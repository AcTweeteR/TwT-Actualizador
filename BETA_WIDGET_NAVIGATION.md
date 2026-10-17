# Widget-navigation Beta

Base: official main a890e627dd1254ff51f412f7144ccde2ad814d51.
Only `/docs/testing/` announces the Beta skin. The stable `/repo/` and
`/docs/repo/` feeds and their artifacts must remain unchanged.
Service 0.4.33 and the verified layout-v12 migration remain unchanged.

## Evidence before the Beta skin

Lenovo TB330FU, Kodi 21.3, skin 1.2.28:

- Active XML identifies recent movies as fixedlist 6042, horizontal,
  width 100%, height 341, widgetExpandable=true, provider recent route,
  actweeter_expand=1 and limit=20. No provider credentials were collected.
- D-pad down changes rows; right advances selection and eventually changes
  the visible recent-movies page. Therefore the container is not globally
  disabled and is not limited to the initially visible posters.
- Horizontal ADB drags at y=850 did not advance as intended. Some returned
  to the first visible page. This observation alone does not identify the
  receiving control, event or complete cause.
- Taps on two different posters opened their corresponding information
  dialogs; diagnostics reported source 6042 and positions 1 and 2.
- The screen-fixed focus border remained at the first poster even when
  right-arrow selection changed. It conflicts with movement=7.

## Source-confirmed defects addressed

Kodi's `CGUIBaseContainer::OnClick` runs matching XML onclick actions instead
of the provider's default folder action. AcTweeteR diagnostic onclick actions
match while diagnostics are enabled, including on the EXPANDIR folder, but
the media-specific Action(info) does not. The Beta adds explicit native
Videos-window navigation to the folder's existing provider path. No new
provider route is constructed.

The native focused poster layout now draws its own border. The stale
screen-fixed overlay is removed from the shared Home/hub surface. The
poster, actions, IDs, movement and media data remain unchanged.

The optional existing diagnostics show live counts/cursor and current
control in Home, Movies and Series. Labels and images are noninteractive;
no raw gestures, hit-test receiver, titles or paths are claimed/recorded.

Engine references (Kodi 21.3-Omega):
- `xbmc/guilib/GUIBaseContainer.cpp`: OnClick, OnMouseEvent.
- `xbmc/guilib/GUIFixedListContainer.cpp`: GetCursorRange, SelectItemFromPoint.
- `xbmc/guilib/GUIControlGroupList.cpp`: SendMouseEvent, IsControlOnScreen.
- `xbmc/guilib/GUIWindow.cpp`: OnMouseAction and exclusive mouse routing.

## Acceptance still required

Install this version through repository.actweeter.testing only. Record live
counts and positions before/during/after a horizontal gesture, compare D-pad
navigation, reach item 21 where a route actually has more than 20 matches,
tap EXPANDIR, verify complete-category navigation and Back. Repeat on more
than one row. No stable promotion until the functional gate passes.

Rollback uses Kodi's native Versions selector and the unchanged stable
repository packages. Do not restore or overwrite profile files for a skin
rollback. The pre-existing restricted Lenovo backup remains available.
