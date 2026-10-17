"""Versioned profile-local Skin Shortcuts v2 data; no provider credentials."""
from __future__ import annotations

import ast
import errno
import fnmatch
import datetime
import hashlib
import json
import os
import re
import uuid
import time
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path

LAYOUT_VERSION = 12
LAYOUT_MIGRATION_ID = 'interface-layout-v12-skinshortcuts-property-identities'
GROUPS = ('mainmenu', 'inicio-1', '10000-1', 'moviehub', 'tvshowhub')
BUILD_COMMAND = ('RunScript(script.skinshortcuts,type=buildxml&mainmenuID=900&levels=1&'
                 'group=mainmenu|powermenu|searchmenu|tmdbsearchmenu|moviehub|tvshowhub|'
                 'newhub|musichub|customhub|somethinghub|mylisthub)')
LAYOUT_XML_VERIFY_INTERVAL_SECONDS = 0.5
BASE = 'plugin://plugin.video.xstream-pro/?mode=premium&view=trending&stype='
SETTINGS = {'spotlighthome.path': BASE+'movie',
            'spotlightmovies.path': BASE+'movie',
            'spotlighttvshows.path': BASE+'series'}
EXPANDABLE_PREMIUM_VIEWS = {
    '', 'continue', 'recent', 'trending', 'popular', 'favorites',
    'series_recent', 'premiere', 'year', 'genre', 'catalog'
}
EXPANSION_QUERY = '&actweeter_expand=1&limit=20'
BUILD_RETRY_DELAYS = (1.0, 2.0, 4.0, 8.0, 15.0)
RETRYABLE_INTERFACE_RESULTS = frozenset({
    # PREPARATION_BUSY means another AcTweeteR coordinator owns the exclusive
    # profile lock. Retrying it would queue a second complete build behind the
    # first one; the active owner is responsible for finishing this operation.
    'BUILD_BUSY', 'BUILD_NOT_CONFIRMED', 'BUILD_TIMEOUT',
    'BUILD_OUTPUT_INVALID', 'GENERATED_XML_PROPERTY_MISSING',
    'GENERATED_IDENTITY_INVALID',
})


def expandable_widget_action(action):
    """Mark only provider list routes supported by the bundled XStream patch.

    Do not parse a full plugin URL from a skin boolean condition. Kodi's
    String.Contains condition expects an info label, and dynamic route text can
    contain skin expressions that make the boolean expression invalid.
    """
    try:
        parsed = urllib.parse.urlsplit(action)
        query = dict(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))
    except (TypeError, ValueError):
        return action, False
    if (parsed.scheme != 'plugin' or parsed.netloc != 'plugin.video.xstream-pro'
            or query.get('mode') != 'premium'
            or query.get('stype') not in ('movie', 'series', 'both')
            or query.get('view', '') not in EXPANDABLE_PREMIUM_VIEWS):
        return action, False
    if any(key.lower() in {'username', 'password', 'token', 'auth', 'url', 'server', 'api_key'}
           for key in query):
        return action, False
    if query.get('actweeter_expand') == '1' and query.get('limit') == '20':
        return action, True
    separator = '&' if parsed.query else '?'
    return action + separator + EXPANSION_QUERY.lstrip('&'), True

class KodiPath:
    """Profile XML must use Kodi VFS: tvOS may keep it in NSUserDefaults."""
    def __init__(self,path,vfs):self.path=str(path);self.vfs=vfs
    def __str__(self):return self.path
    def __truediv__(self,name):return KodiPath(self.path.rstrip('/')+'/'+str(name),self.vfs)
    @property
    def name(self):return self.path.rstrip('/').rsplit('/',1)[-1]
    @property
    def parent(self):return KodiPath(self.path.rstrip('/').rsplit('/',1)[0],self.vfs)
    @property
    def suffix(self):return Path(self.name).suffix
    def exists(self):return self.vfs.exists(self.path)
    def is_file(self):return self.exists() and not self.path.endswith('/')
    def is_symlink(self):return Path(self.vfs.translatePath(self.path)).is_symlink()
    def mkdir(self,**kwargs):
        if not self.vfs.mkdirs(self.path) and not self.vfs.exists(self.path):raise OSError('VFS directory unavailable')
    def read_bytes(self):
        file=self.vfs.File(self.path)
        try:return bytes(file.readBytes())
        finally:file.close()
    def write_bytes(self,data):
        self.parent.mkdir(parents=True,exist_ok=True)
        file=self.vfs.File(self.path,'w')
        try:
            if not file.write(data):raise OSError('VFS write failed')
        finally:file.close()
        if self.read_bytes()!=data:raise OSError('VFS readback mismatch')
    def unlink(self):
        if not self.vfs.delete(self.path):raise OSError('VFS delete failed')
    def glob(self,pattern):
        directories,files=self.vfs.listdir(self.path)
        return [self/name for name in files if fnmatch.fnmatch(name,pattern)]

def as_path(path):return path if isinstance(path,KodiPath) else Path(path)

def digest(data):
    return hashlib.sha256(data).hexdigest()

def atomic_write(path, data):
    if isinstance(path,KodiPath):
        path.write_bytes(data)
        return
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name+'.actweeter-'+uuid.uuid4().hex)
    try:
        with temporary.open('xb') as stream:
            os.chmod(temporary, 0o600)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists(): temporary.unlink()

def load_state(path):
    try:
        value = json.loads(Path(path).read_text(encoding='utf-8'))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def remove_stale_preparation_lock(lock, current_pid=None):
    """Remove only a positively stale lock whose bytes stayed unchanged."""
    lock = Path(lock)
    if lock.is_symlink() or not lock.is_file():
        return False
    try:
        original = lock.read_bytes()
        state = json.loads(original.decode('utf-8'))
        owner_pid = state.get('pid')
    except (OSError, ValueError, UnicodeDecodeError):
        return False
    if type(owner_pid) is not int or owner_pid <= 0 or owner_pid == (current_pid or os.getpid()):
        return False
    probe = getattr(os, 'kill', None)
    if probe is None:
        return False
    try:
        probe(owner_pid, 0)
        return False
    except ProcessLookupError:
        pass
    except (OSError, ValueError) as exc:
        # ESRCH is the only portable evidence that the owner is gone.
        if not isinstance(exc, OSError) or getattr(exc, 'errno', None) != errno.ESRCH:
            return False
    try:
        if lock.is_symlink() or lock.read_bytes() != original:
            return False
        lock.unlink()
        return True
    except OSError:
        return False

def interface_migration_due(state):
    """Return whether the current layout generation still needs Kodi to build it.

    The onboarding flow is process-scoped, but skin updates are not. A verified
    older layout must therefore be rebuilt independently when Home is revisited
    after an add-on update. A current generation is considered complete only
    after Skin Shortcuts output was inspected and marked VERIFIED.
    """
    state = state if isinstance(state, dict) else {}
    try:
        version = int(state.get('layout_version', 0) or 0)
    except (TypeError, ValueError):
        version = 0
    if version < LAYOUT_VERSION:
        return True
    history = state.get('migration_history', [])
    if not isinstance(history, list):
        return True
    current = next((row for row in reversed(history)
                    if isinstance(row, dict) and row.get('id') == LAYOUT_MIGRATION_ID), None)
    return not (state.get('build_status') == 'GENERATED'
                and isinstance(current, dict) and current.get('status') == 'VERIFIED')

def source_documents(skin_root, *, recommendations_enabled=True):
    output = {}
    for group in GROUPS:
        data = (as_path(skin_root)/'shortcuts'/(group+'.DATA.xml')).read_bytes()
        root = ET.fromstring(data)
        if root.tag != 'shortcuts': raise ValueError('invalid shortcut document')
        changed = False
        if group in ('moviehub', 'tvshowhub') and not recommendations_enabled:
            for node in list(root.findall('shortcut')):
                if node.findtext('label') == 'Recomendaciones para ti':
                    root.remove(node)
                    changed = True
        for node in root.findall('shortcut'):
            if node.find('label2') is None or not node.findtext('action'):
                raise ValueError('invalid shortcut item')
            action_node = node.find('action')
            action = action_node.text or ''
            if group != 'mainmenu' and not action.startswith('plugin://plugin.video.xstream-pro/'):
                raise ValueError('non-provider widget source')
            if 'profile_num=' in action or '/Users/' in action:
                raise ValueError('installation-specific widget source')
            if group != 'mainmenu':
                expanded_action, expandable = expandable_widget_action(action)
                if expanded_action != action:
                    action_node.text = expanded_action
                    changed = True
                # Skin Shortcuts 2.x does not promote arbitrary <property>
                # children from a .DATA.xml shortcut into its template item.
                # Custom values must be supplied through its additional-
                # properties store (see expandable_property_rows below).
                for property_node in list(node.findall('property')):
                    if property_node.get('name') == 'widgetExpandable':
                        node.remove(property_node)
                        changed = True
                if expandable:
                    # A stable defaultID lets Skin Shortcuts match the
                    # profile-local custom-property record even if the
                    # displayed label is localized or dynamic.
                    default_id = node.find('defaultID')
                    if default_id is None:
                        action_key = hashlib.sha256(expanded_action.encode('utf-8')).hexdigest()[:20]
                        default_id = ET.SubElement(node, 'defaultID')
                        default_id.text = 'actweeter-expand-%s-%s' % (group, action_key)
                        changed = True
        key = 'skin.actweeter-'+group+'.DATA.xml'
        output[key] = (ET.tostring(root, encoding='utf-8', xml_declaration=True) + b'\n'
                       if changed else data)
    return output


def expandable_shortcut_ids(documents):
    """Map AcTweeteR-owned default IDs to their source DATA group."""
    result = {}
    for filename, data in documents.items():
        if not filename.startswith('skin.actweeter-') or not filename.endswith('.DATA.xml'):
            continue
        group = filename[len('skin.actweeter-'):-len('.DATA.xml')]
        if group == 'mainmenu':
            continue
        root = ET.fromstring(data)
        for shortcut in root.findall('shortcut'):
            action = shortcut.findtext('action', '')
            if not expandable_widget_action(action)[1]:
                continue
            default_id = shortcut.findtext('defaultID', '')
            if not default_id:
                raise ValueError('expandable shortcut missing stable defaultID')
            if default_id in result:
                raise ValueError('duplicate AcTweeteR expandable defaultID')
            result[default_id] = group
    return result


def generated_shortcut_identities(path, expected_ids):
    """Resolve actual group/labelID from Skin Shortcuts generated items.

    Skin Shortcuts 2.x property records are keyed by the generated item
    identity, not by the source DATA filename or defaultID. Read the generated
    include only after its build has stopped. Values are taken from each
    generated item's property children, as Skin Shortcuts itself emits them.
    """
    try:
        root = ET.fromstring(as_path(path).read_bytes())
    except (OSError, ET.ParseError) as exc:
        raise ValueError('generated Skin Shortcuts include is unavailable') from exc
    expected = set(expected_ids)
    found = {}
    for item in root.iter('item'):
        properties = {}
        for prop in item.findall('property'):
            name = prop.get('name')
            if name:
                properties[name] = (prop.text or '').strip()
        default_id = properties.get('defaultID', '')
        if default_id not in expected:
            continue
        identity = (properties.get('group', ''), properties.get('labelID', ''))
        if not all(identity):
            raise ValueError('generated widget is missing group or labelID')
        if default_id in found and found[default_id] != identity:
            raise ValueError('ambiguous generated identity for expandable widget')
        found[default_id] = identity
    # Skin Shortcuts only emits shortcuts that are active in the current
    # profile/menu. Source DATA files also contain defaults for other menu
    # groups (for example group 10000-1) that may not be materialized. Those
    # inactive defaults have no runtime identity to persist yet. Active rows
    # are still enforced after the second build by generated_rows()'s
    # expansion_ready check.
    return found


def expandable_property_rows(documents, identities):
    """Build the four-field rows consumed by Skin Shortcuts 2.0.3."""
    rows = []
    for default_id, source_group in expandable_shortcut_ids(documents).items():
        actual = identities.get(default_id)
        # No Skin Shortcuts property row can be keyed until the default is
        # materialized in the generated includes. A future build will add it.
        if actual is None:
            continue
        if not actual or len(actual) != 2 or not all(actual):
            raise ValueError('missing generated Skin Shortcuts identity')
        rows.append([actual[0], actual[1], 'widgetExpandable', 'true'])
    return rows


def merge_expandable_properties(existing, required_rows):
    """Append AcTweeteR values while preserving every valid user row."""
    if existing is None:
        current = []
    else:
        raw = existing.decode('utf-8')
        try:
            current = json.loads(raw)
        except json.JSONDecodeError:
            current = ast.literal_eval(raw)
        if not isinstance(current, list):
            raise ValueError('invalid Skin Shortcuts properties list')
        for row in current:
            if not isinstance(row, (list, tuple)) or len(row) < 4:
                raise ValueError('invalid Skin Shortcuts property row')

    merged = list(current)
    for required in required_rows:
        group, label_id, name, value = required
        matches = [row for row in merged
                   if len(row) == 4 and row[0] == group and row[1] == label_id
                   and row[2] == name]
        if matches:
            if any(row[3] != value for row in matches):
                raise ValueError('conflicting AcTweeteR Skin Shortcuts property')
            continue
        merged.append(required)
    return json.dumps(merged, ensure_ascii=False, indent=4).encode('utf-8')

def apply_layout(shortcuts_root, service_root, skin_root, current_settings,
                 *, consent=False, snapshots=None, writer=atomic_write,
                 recommendations_enabled=True):
    """Seed absent files; update only bytes we own; back up before mutation.

    APPLIED means DATA/settings have been prepared, not that a widget rendered.
    Skin Shortcuts must build and runtime observation must verify the result.
    """
    shortcuts_root, service_root = as_path(shortcuts_root), Path(service_root)
    state_path = service_root/'interface_layout_state.json'
    state = load_state(state_path)
    documents = source_documents(skin_root,
                                 recommendations_enabled=recommendations_enabled)
    conflicts, changes = [], {}
    for name, wanted in documents.items():
        path = shortcuts_root/name
        if path.is_symlink(): raise ValueError('shortcut symlink refused')
        old = path.read_bytes() if path.is_file() else None
        if old == wanted: continue
        if old is not None and digest(old) != state.get('files',{}).get(name):
            conflicts.append(name)
        changes[name] = wanted
    properties = shortcuts_root/'skin.actweeter.properties'
    if properties.is_symlink(): raise ValueError('Skin Shortcuts properties symlink refused')
    if properties.exists() and not properties.is_file():
        raise ValueError('Skin Shortcuts properties path is not a file')
    # Expandability properties cannot be written from DATA.xml source names:
    # Skin Shortcuts 2.0.3 persists four-field rows keyed by the runtime
    # generated (group, labelID). These identities are learned after the first
    # native build, then written by prepare_interface() before a second build.
    setting_changes = {}
    for key,wanted in SETTINGS.items():
        old = str(current_settings.get(key,'') or '')
        if old == wanted: continue
        if old and old != state.get('settings',{}).get(key): conflicts.append(key)
        setting_changes[key] = wanted
    if conflicts and not consent:
        return {'status':'CONSENT_REQUIRED','conflicts':sorted(set(conflicts))}
    if not changes and not setting_changes and state.get('layout_version') == LAYOUT_VERSION:
        return {'status':'CURRENT','backup':state.get('backup',''),'settings':{},'changed':[]}

    service_root.mkdir(parents=True,exist_ok=True)
    backup = service_root/'interface_backups'/(
        datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8])
    backup.mkdir(parents=True,mode=0o700)
    originals = {}
    manifest = {'schema':1,'files':{},'settings':{k:current_settings.get(k,'') for k in SETTINGS}}
    targets = {name:shortcuts_root/name for name in documents}
    targets.update({properties.name:properties,'skin.actweeter.hash':shortcuts_root/'skin.actweeter.hash'})
    targets['previous-state.json']=state_path
    targets.update(snapshots or {})
    for name,path in targets.items():
        path = as_path(path)
        if path.is_symlink(): raise ValueError('backup symlink refused')
        if path.is_file():
            data = path.read_bytes()
            atomic_write(backup/name,data)
            if (backup/name).read_bytes()!=data: raise OSError('backup readback mismatch')
            manifest['files'][name] = {'exists':True,'sha256':digest(data),'bytes':len(data)}
        else: manifest['files'][name] = {'exists':False}
    atomic_write(backup/'MANIFEST.json',json.dumps(manifest,sort_keys=True,indent=2).encode())
    try:
        for name,data in changes.items():
            path = shortcuts_root/name
            originals[name] = path.read_bytes() if path.is_file() else None
            writer(path,data)
            if path.read_bytes()!=data: raise OSError('shortcut readback mismatch')
        old_version = int(state.get('layout_version', 0) or 0)
        history = list(state.get('migration_history', []))
        migration = {
            'id': LAYOUT_MIGRATION_ID,
            'from_version': old_version,
            'to_version': LAYOUT_VERSION,
            'status': 'APPLIED_PENDING_BUILD',
            'backup': backup.name,
            'checked_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        history = [row for row in history
                   if not isinstance(row, dict) or row.get('id') != LAYOUT_MIGRATION_ID]
        history.append(migration)
        new_state={'layout_version':LAYOUT_VERSION,'files':{n:digest(d) for n,d in documents.items()},
                   'settings':dict(SETTINGS),'backup':backup.name,'build_status':'PENDING',
                   'migration_history':history[-20:]}
        if properties.name in changes:
            new_state['properties_hash']=digest(changes[properties.name])
        elif properties.is_file():
            new_state['properties_hash']=digest(properties.read_bytes())
        atomic_write(state_path,json.dumps(new_state,sort_keys=True,indent=2).encode())
    except Exception:
        for name,original in originals.items():
            path=shortcuts_root/name
            if original is None:
                if path.exists():path.unlink()
            else:atomic_write(path,original)
        raise
    return {'status':'APPLIED','changed':sorted(changes),'settings':setting_changes,
            'backup':backup.name,'migration':migration}

def rollback_layout(shortcuts_root,service_root):
    shortcuts_root,service_root=as_path(shortcuts_root),Path(service_root)
    state_path=service_root/'interface_layout_state.json'
    state=load_state(state_path)
    if not re_safe_name(state.get('backup')):return None
    backup=service_root/'interface_backups'/state['backup']
    manifest=load_state(backup/'MANIFEST.json')
    names=list(state.get('files',{}))+['skin.actweeter.properties']
    for name in names:
        path=shortcuts_root/name
        expected=state.get('files',{}).get(name) or state.get('properties_hash')
        if path.is_file() and (expected is None or digest(path.read_bytes())!=expected):
            return None
    for name in names:
        info=manifest.get('files',{}).get(name,{})
        path=shortcuts_root/name
        if info.get('exists'):
            data=(backup/name).read_bytes()
            if digest(data)!=info['sha256']:raise OSError('backup integrity mismatch')
            atomic_write(path,data)
        elif path.exists():path.unlink()
    previous=manifest.get('files',{}).get('previous-state.json',{})
    if previous.get('exists'):atomic_write(state_path,(backup/'previous-state.json').read_bytes())
    elif state_path.exists():state_path.unlink()
    return manifest.get('settings',{})

def generated_rows(path):
    """Read generated widget descriptors for diagnostics, never claim rendering."""
    result={}
    try:root=ET.fromstring(as_path(path).read_bytes())
    except (OSError,ET.ParseError):return result
    for name in ('Widgets','moviehub','tvshowhub'):
        inc=root.find("include[@name='skinshortcuts-template-%s']"%name)
        rows=[]
        def nodes(element,visited):
            for node in element.iter('include'):
                yield node
                reference=(node.text or '').strip()
                if reference and reference not in visited:
                    target=root.find("include[@name='%s']"%reference)
                    if target is not None:
                        yield from nodes(target,visited|{reference})
        if inc is not None:
            for node in nodes(inc,{inc.get('name')}):
                params={p.get('name'):p.get('value','') for p in node.findall('param')}
                route=params.get('widgetPath') or params.get('path')
                if route:
                    sensitive=any(k.lower() in ('username','password','token','auth','url','server','api_key')
                                  for k in urllib.parse.parse_qs(urllib.parse.urlparse(route).query))
                    provider_only=route.startswith('plugin://plugin.video.xstream-pro/') and not sensitive
                    query=urllib.parse.parse_qs(urllib.parse.urlparse(route).query)
                    route_expandable=expandable_widget_action(route)[1] if provider_only else False
                    metadata_expandable=params.get('widgetExpandable','').strip().lower()=='true'
                    route_has_expansion=(query.get('actweeter_expand')==['1']
                                         and query.get('limit')==['20'])
                    expansion_ready=(not route_expandable or
                                      (metadata_expandable and route_has_expansion))
                    rows.append({'label':params.get('widgetName') or params.get('label',''),
                                 'provider_only':provider_only,
                                 'expandable':metadata_expandable,
                                 'expansion_ready':expansion_ready,
                                 'route':route if provider_only else '[REDACTED_OR_NON_PROVIDER_SOURCE]'})
        result[name]=rows
    return result


def generated_layout_ready(path, shortcuts_root, documents):
    """Verify materialized widgets and their profile properties before reuse.

    This is deliberately stricter than checking that an include file exists:
    a routine Home startup may skip Skin Shortcuts only when the active output
    contains every expected widget group, safe provider routes, expansion
    metadata, and the matching four-field properties in Skin Shortcuts' store.
    """
    rows = generated_rows(path)
    if (not all(len(rows.get(group, [])) >= count for group, count in
                (('Widgets', 6), ('moviehub', 10), ('tvshowhub', 10)))
            or not all(row['provider_only'] and row['expansion_ready']
                       for group in rows.values() for row in group)):
        return False, rows
    try:
        identities = generated_shortcut_identities(
            path, expandable_shortcut_ids(documents))
    except ValueError:
        return False, rows
    return verify_expandable_property_store(
        shortcuts_root, documents, identities), rows


def can_reuse_generated_layout(layout_status, metadata_refreshed, ready,
                               migration_verified):
    """Only reuse output when source, prior migration, and generated XML verify."""
    return (layout_status == 'CURRENT' and not metadata_refreshed
            and bool(ready) and bool(migration_verified))


def second_layout_build_needed(properties_changed, first_output_ready):
    """A second build is needed only if persistence changed or output is stale."""
    return bool(properties_changed) or not bool(first_output_ready)


def persist_generated_expandable_properties(shortcuts_root, service_root,
                                            generated_path, documents):
    """Backup and persist properties using identities from a completed build."""
    shortcuts_root, service_root = as_path(shortcuts_root), Path(service_root)
    properties = shortcuts_root/'skin.actweeter.properties'
    if properties.is_symlink():
        raise ValueError('Skin Shortcuts properties symlink refused')
    existing = properties.read_bytes() if properties.is_file() else None
    ids = expandable_shortcut_ids(documents)
    identities = generated_shortcut_identities(generated_path, ids)
    required = expandable_property_rows(documents, identities)
    merged = merge_expandable_properties(existing, required)
    if merged == existing:
        return {'changed': False, 'rows': len(required), 'identities': identities}

    # Keep a dedicated, verified pre-write copy. This also covers retries where
    # the DATA migration was already applied by an earlier attempt.
    backup = service_root/'interface_backups'/(
        datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+
        '-properties-'+uuid.uuid4().hex[:8])
    backup.mkdir(parents=True, mode=0o700)
    manifest = {'schema': 1, 'files': {}}
    if existing is not None:
        atomic_write(backup/'skin.actweeter.properties', existing)
        if (backup/'skin.actweeter.properties').read_bytes() != existing:
            raise OSError('Skin Shortcuts property backup readback mismatch')
        manifest['files']['skin.actweeter.properties'] = {
            'exists': True, 'sha256': digest(existing), 'bytes': len(existing)}
    else:
        manifest['files']['skin.actweeter.properties'] = {'exists': False}
    atomic_write(backup/'MANIFEST.json', json.dumps(
        manifest, sort_keys=True, indent=2).encode('utf-8'))
    try:
        atomic_write(properties, merged)
        if properties.read_bytes() != merged:
            raise OSError('Skin Shortcuts property persistence readback mismatch')
        state_path = service_root/'interface_layout_state.json'
        state = load_state(state_path)
        state['properties_hash'] = digest(merged)
        state['properties_backup'] = backup.name
        atomic_write(state_path, json.dumps(state, sort_keys=True, indent=2).encode('utf-8'))
    except Exception:
        # Roll back only if our exact bytes are still present; never overwrite
        # a concurrent Kodi/user change made after the attempted write.
        if properties.is_file() and digest(properties.read_bytes()) == digest(merged):
            if existing is None:
                properties.unlink()
            else:
                atomic_write(properties, existing)
        raise
    return {'changed': True, 'rows': len(required), 'identities': identities,
            'backup': backup.name}


def verify_expandable_property_store(shortcuts_root, documents, identities):
    """Re-read the persisted profile data using Skin Shortcuts' exact key."""
    path = as_path(shortcuts_root)/'skin.actweeter.properties'
    try:
        raw = path.read_bytes().decode('utf-8')
        try:
            stored = json.loads(raw)
        except ValueError:
            stored = ast.literal_eval(raw)
    except (OSError, ValueError, SyntaxError, UnicodeDecodeError):
        return False
    if not isinstance(stored, list):
        return False
    required = expandable_property_rows(documents, identities)
    for group, label_id, name, value in required:
        matches = [row for row in stored if isinstance(row, (list, tuple))
                   and len(row) == 4 and row[0] == group and row[1] == label_id
                   and row[2] == name]
        if not matches or any(row[3] != value for row in matches):
            return False
    return True


def request_skinshortcuts_build(kodi, window, monitor, generated_path,
                                *, timeout=30.0, start_timeout=5.0,
                                poll_interval=0.05, phase='unspecified',
                                correlation_id=None):
    """Request and observe one native build; Kodi builtins have no result value."""
    correlation_id = correlation_id or uuid.uuid4().hex[:12]
    if window.getProperty('skinshortcuts-isrunning') == 'True':
        return 'BUILD_BUSY'
    before = None
    try:
        before = digest(as_path(generated_path).read_bytes())
    except OSError:
        pass
    kodi.log('[AcTweeteR] SKINSHORTCUTS_BUILD status=requested phase=%s id=%s' %
             (phase, correlation_id), kodi.LOGINFO)
    kodi.executebuiltin(BUILD_COMMAND, False)
    started_at = time.monotonic()
    deadline = started_at + timeout
    start_deadline = min(deadline, started_at + start_timeout)
    observed_running = False
    while not monitor.abortRequested() and time.monotonic() < deadline:
        running = window.getProperty('skinshortcuts-isrunning') == 'True'
        if running:
            observed_running = True
        elif observed_running:
            after = None
            try:
                after = digest(as_path(generated_path).read_bytes())
            except OSError:
                pass
            kodi.log('[AcTweeteR] SKINSHORTCUTS_BUILD status=finished phase=%s id=%s output_changed=%s' %
                     (phase, correlation_id,
                      'true' if after is not None and after != before else 'false'),
                     kodi.LOGINFO)
            return 'BUILD_FINISHED'
        else:
            after = None
            try:
                after = digest(as_path(generated_path).read_bytes())
            except OSError:
                pass
            if after is not None and before is not None and after != before:
                kodi.log('[AcTweeteR] SKINSHORTCUTS_BUILD status=finished_without_running_signal phase=%s id=%s output_changed=true' %
                         (phase, correlation_id),
                         kodi.LOGINFO)
                return 'BUILD_FINISHED'
            if time.monotonic() >= start_deadline:
                kodi.log('[AcTweeteR] SKINSHORTCUTS_BUILD status=start_not_observed phase=%s id=%s' %
                         (phase, correlation_id),
                         kodi.LOGWARNING)
                return 'BUILD_NOT_CONFIRMED'
        if monitor.waitForAbort(poll_interval):
            return 'ABORTED'
    kodi.log('[AcTweeteR] SKINSHORTCUTS_BUILD status=timeout phase=%s id=%s observed_running=%s' %
             (phase, correlation_id,
              'true' if observed_running else 'false'), kodi.LOGWARNING)
    return 'BUILD_TIMEOUT' if observed_running else 'BUILD_NOT_CONFIRMED'


def retry_interface_preparation(prepare, wait, *, on_attempt=None,
                                on_retry=None, delays=BUILD_RETRY_DELAYS):
    """Run a bounded retry policy; wait returns True when Kodi aborts."""
    for attempt in range(1, len(delays) + 2):
        if on_attempt:
            on_attempt(attempt, len(delays) + 1)
        result = prepare()
        if result not in RETRYABLE_INTERFACE_RESULTS:
            return result, attempt
        if attempt > len(delays):
            return result, attempt
        delay = delays[attempt - 1]
        if on_retry:
            on_retry(result, delay)
        if wait(delay):
            return 'ABORTED', attempt
    return 'BUILD_NOT_CONFIRMED', len(delays) + 1

def layout_validation_due(build_running, now, next_check,
                          interval=LAYOUT_XML_VERIFY_INTERVAL_SECONDS):
    """Avoid parsing generated XML while Skin Shortcuts is still building it."""
    if build_running or float(now) < float(next_check):
        return False, float(next_check)
    return True, float(now) + max(0.1, float(interval))

def inspect_generated_layout(path, build_running, now, next_check):
    """Parse once after a build completes, then retry at a bounded cadence."""
    due,next_check=layout_validation_due(build_running,now,next_check)
    return (generated_rows(path) if due else None),next_check,due

def publish_years(window, now=None):
    year=(now or datetime.datetime.now()).year
    window.setProperty('AcTweeteR.CurrentYear',str(year))
    window.setProperty('AcTweeteR.PreviousYear',str(year-1))

def refresh_recommendations(window, builtin):
    """Invalidate Kodi's route cache after the user authorizes XStream in its UI."""
    window.setProperty('AcTweeteR.TraktRecommendationsRefresh', str(time.time_ns()))
    builtin('Container.Refresh', True)

def prepare_metadata_language(addon_factory,vfs,service_root):
    """Configure verified public settings, retaining credentials and custom languages."""
    addon=addon_factory('plugin.video.xstream-pro')
    desired={'tmdb_language':'es-ES','interface_language':'Español'}
    defaults={'tmdb_language':('','en-US'),'interface_language':('','English')}
    previous={key:addon.getSetting(key) for key in desired}
    changes={key:value for key,value in desired.items() if previous[key] in defaults[key]}
    root=Path(service_root)
    migration=load_state(root/'metadata_preferences.json')
    spanish=(previous['tmdb_language'].lower().replace('_','-').split('-')[0]=='es')
    refresh_spanish_cache=spanish and migration.get('schema')!=1
    if not changes and not refresh_spanish_cache:return {'changed':False,'settings':previous}
    backup=root/'metadata_backups'/uuid.uuid4().hex[:12]
    backup.mkdir(parents=True,mode=0o700)
    atomic_write(backup/'preferences.json',json.dumps(previous,ensure_ascii=False).encode())
    profile=Path(vfs.translatePath(addon.getAddonInfo('profile')))
    cache_files=[p for p in profile.glob('data_cache_p*_premium_meta_*_es.json')
                 if re.fullmatch(r'data_cache_p[0-9]+_premium_meta_(movie|series)_[0-9]+_es\.json',p.name)]
    for path in cache_files:
        if path.is_symlink():raise ValueError('metadata cache symlink refused')
        data=path.read_bytes();atomic_write(backup/path.name,data)
        if (backup/path.name).read_bytes()!=data:raise OSError('metadata backup failed')
    try:
        for key,value in changes.items():
            addon.setSetting(key,value)
            if addon.getSetting(key)!=value:raise OSError('metadata setting not persisted')
        if 'tmdb_language' in changes or refresh_spanish_cache:
            for path in cache_files:path.unlink()
    except Exception:
        for key in changes:addon.setSetting(key,previous[key])
        for path in cache_files:
            if not path.exists():atomic_write(path,(backup/path.name).read_bytes())
        raise
    report={'schema':1,'changed':bool(changes),'settings':{key:addon.getSetting(key) for key in desired},
            'backup':backup.name,'refreshed_metadata_entries':len(cache_files)}
    atomic_write(root/'metadata_preferences.json',json.dumps(report,ensure_ascii=False).encode())
    return report

def prepare_interface(kodi, addon_factory, vfs, gui, dialog, *, allow_prompt=False):
    service_root=Path(vfs.translatePath(addon_factory('service.actweeter').getAddonInfo('profile')))
    service_root.mkdir(parents=True,exist_ok=True)
    lock=service_root/'interface-prepare.lock'
    try:descriptor=os.open(lock,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    except FileExistsError:
        previous=load_state(lock)
        if remove_stale_preparation_lock(lock, os.getpid()):
            return prepare_interface(kodi,addon_factory,vfs,gui,dialog,allow_prompt=allow_prompt)
        return 'PREPARATION_BUSY'
    try:
        with os.fdopen(descriptor,'w') as stream:json.dump({'pid':os.getpid()},stream)
        return _prepare_interface(kodi,addon_factory,vfs,gui,dialog,allow_prompt=allow_prompt)
    finally:
        if lock.exists():lock.unlink()

def _prepare_interface(kodi, addon_factory, vfs, gui, dialog, *, allow_prompt=False):
    """Kodi adapter: prepare DATA then ask Skin Shortcuts to generate its includes."""
    window=gui.Window(10000)
    publish_years(window)
    if kodi.getSkinDir()!='skin.actweeter':return 'OTHER_SKIN'
    if kodi.getCondVisibility('Player.HasMedia'):return 'PLAYER_ACTIVE'
    shortcuts=addon_factory('script.skinshortcuts')
    if not shortcuts.getAddonInfo('version').startswith('2.'):
        return 'UNSUPPORTED_SKIN_SHORTCUTS'
    skin=addon_factory('skin.actweeter')
    if not (Path(vfs.translatePath(skin.getAddonInfo('path')))/'shortcuts/inicio-1.DATA.xml').is_file():
        return 'SKIN_UPDATE_REQUIRED'
    service=addon_factory('service.actweeter')
    service_root=Path(vfs.translatePath(service.getAddonInfo('profile')))
    skin_root=Path(vfs.translatePath(skin.getAddonInfo('path')))
    profile=KodiPath('special://profile/',vfs)
    monitor=kodi.Monitor()
    deadline=time.monotonic()+30
    while window.getProperty('skinshortcuts-isrunning')=='True':
        if time.monotonic()>=deadline or monitor.waitForAbort(.1):return 'BUILD_BUSY'
    current={key:kodi.getInfoLabel('Skin.String(%s)'%key) for key in SETTINGS}
    metadata_result=prepare_metadata_language(addon_factory,vfs,service_root)
    snapshots={'skin-settings.xml':profile/'addon_data/skin.actweeter/settings.xml',
               'generated-includes.xml':KodiPath(str(skin_root/'1080i/script-skinshortcuts-includes.xml'),vfs)}
    # The row is structurally present in clean installs and upgrades. XStream's
    # patched native route returns an empty directory unless authorized results
    # have an exact provider TMDb ID; the skin hides empty widget containers.
    recommendations_enabled = True
    result=apply_layout(profile/'addon_data/script.skinshortcuts',service_root,
                        skin_root,current,snapshots=snapshots,
                        recommendations_enabled=recommendations_enabled)
    if result['status']=='CONSENT_REQUIRED':
        if not allow_prompt:return 'CUSTOMIZATIONS_PRESERVED'
        if not dialog.yesno('Diseño de AcTweeteR',
                            'Hay ajustes de interfaz personalizados. ¿Aplicar las filas del proveedor y los años dinámicos? Se guardará una copia de seguridad antes del cambio.',
                            nolabel='Conservar',yeslabel='Aplicar diseño'):
            return 'CUSTOMIZATIONS_PRESERVED'
        result=apply_layout(profile/'addon_data/script.skinshortcuts',service_root,
                            skin_root,current,consent=True,snapshots=snapshots,
                            recommendations_enabled=recommendations_enabled)
    for key,value in result.get('settings',{}).items():
        kodi.executebuiltin('Skin.SetString(%s,%s)'%(key,value),True)
        if kodi.getInfoLabel('Skin.String(%s)'%key)!=value:
            old=rollback_layout(profile/'addon_data/script.skinshortcuts',service_root)
            for old_key,old_value in (old or {}).items():
                kodi.executebuiltin('Skin.SetString(%s,%s)'%(old_key,old_value) if old_value
                                   else 'Skin.Reset(%s)'%old_key,True)
            return 'SETTING_WRITE_FAILED'
    if result['status']=='APPLIED' or metadata_result.get('refreshed_metadata_entries',0):
        window.setProperty('skinshortcuts-reloadmainmenu','True')
    generated_path=snapshots['generated-includes.xml']
    documents=source_documents(skin_root,
                               recommendations_enabled=recommendations_enabled)
    current_ready, _current_rows = generated_layout_ready(
        generated_path, profile/'addon_data/script.skinshortcuts', documents)
    current_state=load_state(service_root/'interface_layout_state.json')
    if can_reuse_generated_layout(
            result['status'], metadata_result.get('refreshed_metadata_entries',0),
            current_ready, not interface_migration_due(current_state)):
        window.setProperty('AcTweeteR.InterfaceReady','1')
        kodi.log('[AcTweeteR] INTERFACE_LAYOUT status=verified_reused reason=current_inputs_and_generated_xml',
                 kodi.LOGINFO)
        return 'GENERATED'

    build_id=uuid.uuid4().hex[:12]
    first_build=request_skinshortcuts_build(
        kodi,window,monitor,generated_path,phase='identity',correlation_id=build_id)
    if first_build!='BUILD_FINISHED':
        kodi.log('[AcTweeteR] INTERFACE_LAYOUT status=build_not_confirmed phase=identity result=%s'%
                 first_build,kodi.LOGWARNING)
        return first_build

    # First native build materializes the real Skin Shortcuts group/labelID
    # identities. Source DATA names (such as inicio-1) are not runtime groups.
    first_rows=generated_rows(generated_path)
    if (not all(len(first_rows.get(group,[]))>=count for group,count in
                (('Widgets',6),('moviehub',10),('tvshowhub',10)))
            or not all(row['provider_only'] for group in first_rows.values()
                       for row in group)):
        return 'BUILD_OUTPUT_INVALID'
    try:
        property_result=persist_generated_expandable_properties(
            profile/'addon_data/script.skinshortcuts',service_root,
            generated_path,documents)
    except (OSError, ValueError, SyntaxError, UnicodeDecodeError) as exc:
        # Exception text is from this module's fixed validation messages and
        # contains no user paths, property values, credentials, or provider URLs.
        kodi.log('[AcTweeteR] INTERFACE_LAYOUT status=property_persistence_failed type=%s reason=%s'%
                 (type(exc).__name__,str(exc)),kodi.LOGERROR)
        return 'PROPERTY_PERSISTENCE_FAILED'
    kodi.log('[AcTweeteR] WIDGET_EXPANDABLE_PROPERTIES status=persisted changed=%s rows=%d inactive_defaults=%d'%
             ('true' if property_result['changed'] else 'false',property_result['rows'],
              max(0,len(expandable_shortcut_ids(documents))-property_result['rows'])),
             kodi.LOGINFO)

    first_ready, first_rows = generated_layout_ready(
        generated_path, profile/'addon_data/script.skinshortcuts', documents)
    if second_layout_build_needed(property_result['changed'], first_ready):
        # The second pass is necessary only when writing the dynamic properties
        # changed Skin Shortcuts' input or the first generated output still
        # lacks a verified expansion property. A no-op first pass with already
        # materialized, verified properties must not trigger another Home reload.
        window.setProperty('skinshortcuts-reloadmainmenu','True')
        second_build=request_skinshortcuts_build(
            kodi,window,monitor,generated_path,phase='property',correlation_id=build_id)
        if second_build!='BUILD_FINISHED':
            kodi.log('[AcTweeteR] INTERFACE_LAYOUT status=build_not_confirmed phase=property result=%s'%
                     second_build,kodi.LOGWARNING)
            return second_build
        rows=generated_rows(generated_path)
    else:
        rows=first_rows
        kodi.log('[AcTweeteR] SKINSHORTCUTS_BUILD status=skipped phase=property reason=unchanged_and_verified',
                 kodi.LOGINFO)
    if (not all(len(rows.get(group,[]))>=count for group,count in
                (('Widgets',6),('moviehub',10),('tvshowhub',10)))
            or not all(row['provider_only'] and row['expansion_ready']
                       for group in rows.values() for row in group)):
        kodi.log('[AcTweeteR] INTERFACE_LAYOUT status=generated_xml_property_missing',
                 kodi.LOGWARNING)
        return 'GENERATED_XML_PROPERTY_MISSING'

    try:
        identities=generated_shortcut_identities(
            generated_path,expandable_shortcut_ids(documents))
    except ValueError as exc:
        kodi.log('[AcTweeteR] INTERFACE_LAYOUT status=generated_identity_invalid type=%s'%
                 type(exc).__name__,kodi.LOGWARNING)
        return 'GENERATED_IDENTITY_INVALID'
    if not verify_expandable_property_store(
            profile/'addon_data/script.skinshortcuts',documents,identities):
        kodi.log('[AcTweeteR] INTERFACE_LAYOUT status=property_store_verification_failed',
                 kodi.LOGWARNING)
        return 'GENERATED_XML_PROPERTY_MISSING'
    path=service_root/'interface_layout_state.json'
    state=load_state(path)
    state['build_status']='GENERATED'
    for migration in state.get('migration_history', []):
        if isinstance(migration, dict) and migration.get('id') == LAYOUT_MIGRATION_ID:
            migration['status'] = 'VERIFIED'
            migration['verified_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            migration['property_rows'] = property_result['rows']
    atomic_write(path,json.dumps(state,sort_keys=True,indent=2).encode())
    window.setProperty('AcTweeteR.InterfaceReady','1')
    kodi.log('[AcTweeteR] INTERFACE_LAYOUT migration=%s from=%s to=%s status=verified home=%d movies=%d series=%d'%
             (LAYOUT_MIGRATION_ID, state.get('migration_history', [{}])[-1].get('from_version', 'unknown'),
              LAYOUT_VERSION, len(rows['Widgets']),len(rows['moviehub']),len(rows['tvshowhub'])),kodi.LOGINFO)
    from slyguy_bridge_install import install as install_preview_bridge
    try:
        bridge=install_preview_bridge(kodi,addon_factory,vfs,dialog,allow_prompt=allow_prompt)
        kodi.log('[AcTweeteR] PREVIEW_BRIDGE_INTEGRATION status=%s'%bridge,kodi.LOGINFO)
    except Exception as exc:
        kodi.log('[AcTweeteR] PREVIEW_BRIDGE_INTEGRATION status=failed type=%s'%type(exc).__name__,kodi.LOGWARNING)
    return 'GENERATED'

def interface_report(kodi, addon_factory, vfs):
    skin=addon_factory('skin.actweeter')
    service=addon_factory('service.actweeter')
    service_root=Path(vfs.translatePath(service.getAddonInfo('profile')))
    state=load_state(service_root/'interface_layout_state.json')
    rows=generated_rows(KodiPath(skin.getAddonInfo('path'),vfs)/'1080i/script-skinshortcuts-includes.xml')
    property_path=KodiPath('special://profile/addon_data/script.skinshortcuts/skin.actweeter.properties',vfs)
    property_rows=[]
    legacy_widget_property_rows=0
    try:
        raw=property_path.read_bytes().decode('utf-8')
        try: stored=json.loads(raw)
        except ValueError: stored=ast.literal_eval(raw)
        for row in stored if isinstance(stored,list) else []:
            if isinstance(row,(list,tuple)) and len(row)>=3 and row[2]=='widgetExpandable':
                if len(row)==4:
                    property_rows.append(list(row))
                else:
                    legacy_widget_property_rows+=1
    except (OSError,ValueError,SyntaxError,UnicodeDecodeError):
        pass
    identities={}
    try:
        documents=source_documents(Path(vfs.translatePath(skin.getAddonInfo('path'))))
        identities=generated_shortcut_identities(
            KodiPath(skin.getAddonInfo('path')+'/1080i/script-skinshortcuts-includes.xml',vfs),
            expandable_shortcut_ids(documents))
    except (OSError,ValueError,ET.ParseError):
        identities={}
    backup=state.get('backup','')
    manifest={}
    if re_safe_name(backup):manifest=load_state(service_root/'interface_backups'/backup/'MANIFEST.json')
    previous_backup=load_state(service_root/'interface_backup_only.json')
    language_settings={}
    try:
        xstream=addon_factory('plugin.video.xstream-pro')
        language_settings={key:xstream.getSetting(key) for key in ('tmdb_language','interface_language')}
    except Exception:pass
    migration=next((row for row in reversed(state.get('migration_history',[]))
                    if isinstance(row,dict) and row.get('id')==LAYOUT_MIGRATION_ID),{})
    return {'schema':1,'active_skin':kodi.getSkinDir(),'layout_version':state.get('layout_version'),
            'build_status':state.get('build_status','NOT_PREPARED'),
            'migration_status':migration.get('status','NOT_RECORDED'),
            'widget_expandable_property_rows':property_rows,
            'legacy_widget_expandable_rows_ignored':legacy_widget_property_rows,
            'generated_widget_identities':[
                {'defaultID':default_id,'group':identity[0],'labelID':identity[1]}
                for default_id,identity in sorted(identities.items())],
            'rows':rows,
            'backup':{'id':backup,'files':manifest.get('files',{}),'verified':bool(manifest.get('files'))},
            'pre_update_backup':previous_backup,
            'metadata_preferences':load_state(service_root/'metadata_preferences.json'),
            'metadata_language_settings':language_settings,
            'preview_bridge':load_state(service_root/'slyguy_bridge_integration.json'),
            'visual_validation':'NOT_TESTED'}

def backup_interface(addon_factory,vfs):
    """Backup the affected interface in its own device before updating the skin."""
    service_root=Path(vfs.translatePath(addon_factory('service.actweeter').getAddonInfo('profile')))
    profile=KodiPath('special://profile/',vfs)
    skin_root=Path(vfs.translatePath(addon_factory('skin.actweeter').getAddonInfo('path')))
    shortcuts=profile/'addon_data/script.skinshortcuts'
    targets={'skin-settings.xml':profile/'addon_data/skin.actweeter/settings.xml',
             'generated-includes.xml':KodiPath(str(skin_root/'1080i/script-skinshortcuts-includes.xml'),vfs)}
    for path in shortcuts.glob('skin.actweeter*'):
        if path.suffix in ('.xml','.hash','.properties'):targets[path.name]=path
    backup_id='before-update-'+uuid.uuid4().hex[:12]
    backup=service_root/'interface_backups'/backup_id
    backup.mkdir(parents=True,mode=0o700)
    manifest={'schema':1,'files':{}}
    for name,path in targets.items():
        if path.is_symlink():raise ValueError('backup symlink refused')
        if not path.is_file():continue
        data=path.read_bytes();atomic_write(backup/name,data)
        if (backup/name).read_bytes()!=data:raise OSError('backup readback failed')
        manifest['files'][name]={'sha256':digest(data),'bytes':len(data),'exists':True}
    if 'generated-includes.xml' not in manifest['files'] or 'skin-settings.xml' not in manifest['files']:
        raise OSError('required interface backup missing')
    atomic_write(backup/'MANIFEST.json',json.dumps(manifest,sort_keys=True,indent=2).encode())
    report={'id':backup_id,'verified':True,'files':manifest['files']}
    atomic_write(service_root/'interface_backup_only.json',json.dumps(report,sort_keys=True).encode())
    return report

def re_safe_name(value):
    return isinstance(value,str) and bool(value) and '/' not in value and '\\' not in value and '..' not in value

class SpotlightRotation:
    """Use the existing minute coordinator tick; never change interactive focus."""
    def __init__(self):self.last=0
    def tick(self,kodi,now,active_window=None):
        if not hasattr(kodi,'getCondVisibility'):return
        if active_window is not None and active_window not in (10000,11110,11111):return
        if now-self.last<60:return
        self.last=now
        visible=(kodi.getCondVisibility('Window.IsActive(Home)') or
                 kodi.getCondVisibility('Window.IsActive(1111)') or
                 kodi.getCondVisibility('Window.IsActive(1110)'))
        if not visible or not kodi.getCondVisibility('Control.IsVisible(1508)'):return
        if kodi.getCondVisibility('Player.HasMedia') or kodi.getCondVisibility('Control.HasFocus(1508)'):return
        if kodi.getInfoLabel('Window(Home).Property(AcTweeteR.InterfaceReady)')!='1':return
        if kodi.getInfoLabel('Window(Home).Property(spotlightinfo)'):return
        try:count=int(kodi.getInfoLabel('Container(1508).NumItems') or '0')
        except ValueError:return
        if count>1:kodi.executebuiltin('Control.Move(1508,1)',False)
