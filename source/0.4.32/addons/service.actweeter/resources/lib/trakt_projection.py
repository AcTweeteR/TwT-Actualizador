"""Conservative account-bound watched projection for XStream's two stores."""
import json
import os
from pathlib import Path


def project_watched(plan, *, profile, account, movie_path, episode_path, dry_run=True):
    if str(plan.get('profile')) != str(profile) or plan.get('account') != account:
        raise PermissionError('account/profile binding mismatch')
    if not str(profile).isdigit() or int(profile) < 1 or not account:
        raise ValueError('valid account and profile required')
    movies, episodes = {}, {}
    for item in plan.get('items', []):
        if not item.get('watched'):
            continue
        content = item['identity']
        provider = str(item['provider_id'])
        if not provider.isdigit() or int(provider) < 1:
            raise ValueError('unverified provider identifier')
        if content['kind'] == 'movie':
            movies[provider] = True
        elif content['kind'] == 'episode':
            series = str(item.get('provider_series_id', ''))
            episode = str(item.get('provider_episode_id', ''))
            season = str(content['season'])
            if not series.isdigit() or not episode.isdigit() or not season.isdigit():
                continue
            episodes.setdefault(series, {}).setdefault(season, set()).add(episode)
    result = {'movies': len(movies), 'episodes': sum(len(ids) for seasons in episodes.values()
                                                     for ids in seasons.values()),
              'dry_run': bool(dry_run)}
    if dry_run:
        return result

    def merge(path, updates, nested=False):
        target = Path(path)
        if target.is_symlink() or not target.parent.is_dir():
            raise ValueError('unsafe destination')
        current = json.loads(target.read_text('utf-8')) if target.exists() else {}
        if not isinstance(current, dict):
            raise ValueError('invalid existing watched store')
        if nested:
            for series, seasons in updates.items():
                old = current.setdefault(series, {})
                if not isinstance(old, dict):
                    raise ValueError('invalid existing season data')
                for season, ids in seasons.items():
                    existing = old.setdefault(season, [])
                    if not isinstance(existing, list):
                        raise ValueError('invalid existing episode data')
                    old[season] = existing + sorted(ids - set(map(str, existing)), key=int)
        else:
            current.update(updates)
        tmp = target.with_name(target.name + '.trakt-tmp')
        with tmp.open('x', encoding='utf-8') as stream:
            os.chmod(tmp, 0o600)
            json.dump(current, stream, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, target)

    # The caller stages each store separately; active files are committed transactionally later.
    if movies and episodes:
        raise RuntimeError('mixed-store commit requires transactional coordinator')
    if movies:
        merge(movie_path, movies)
    if episodes:
        merge(episode_path, episodes, nested=True)
    return result
