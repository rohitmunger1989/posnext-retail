"""Customer Display video playlist helpers; uses normal Frappe file uploads."""
from urllib.parse import urlsplit, unquote
from pathlib import PurePosixPath
import frappe
from frappe import _
from frappe.utils import cint

MAX_VIDEO_BYTES = 500 * 1024 * 1024
VIDEO_EXTENSIONS = {'.mp4', '.webm', '.ogg', '.ogv', '.m4v', '.mov'}
PLAYLIST_FIELD = 'customer_display_videos'
CHILD = 'POS Customer Display Video'


def validate_video_url(value):
    value = str(value or '').strip()
    parsed = urlsplit(value)
    if parsed.path.startswith('/private/files/'):
        frappe.throw(_('Customer Display videos must be public files.'))
    if parsed.scheme:
        if parsed.scheme != 'https' or not parsed.netloc or parsed.username or parsed.password:
            frappe.throw(_('Video links must use HTTPS without embedded credentials.'))
    elif parsed.netloc or not parsed.path.startswith('/files/') or '..' in unquote(parsed.path).split('/'):
        frappe.throw(_('Select a public video from Files, upload a video, or use an HTTPS video link.'))
    if not parsed.scheme and PurePosixPath(unquote(parsed.path)).suffix.lower() not in VIDEO_EXTENSIONS:
        frappe.throw(_('Select an MP4, WebM, OGG, M4V or MOV video. MP4 is recommended.'))
    return value


def validate_playlist(doc):
    seen = set()
    for idx, row in enumerate(doc.get(PLAYLIST_FIELD) or [], start=1):
        row.idx = idx
        row.video = validate_video_url(row.get('video'))
        if row.video in seen:
            frappe.throw(_('The video playlist contains a duplicate video.'))
        seen.add(row.video)
        file = frappe.db.get_value('File', {'file_url':row.video}, ['file_size','is_private'], as_dict=True)
        if file:
            if cint(file.is_private):
                frappe.throw(_('Customer Display videos must be public files.'))
            if cint(file.file_size) > MAX_VIDEO_BYTES:
                frappe.throw(_('Each advertising video must be 500 MB or smaller.'))


def attach_playlist(settings):
    settings[PLAYLIST_FIELD] = []
    if settings.get('name') and frappe.db.exists('DocType', CHILD):
        settings[PLAYLIST_FIELD] = frappe.get_all(CHILD,
            filters={'parent':settings['name'],'parenttype':'POS Settings','parentfield':PLAYLIST_FIELD},
            fields=['name','video','title','enabled','idx'],order_by='idx asc')
    return settings


@frappe.whitelist()
def list_advertising_videos(pos_profile):
    name = frappe.db.get_value('POS Settings', {'pos_profile':pos_profile}, 'name')
    if not name:
        frappe.throw(_('Save POS Settings first.'))
    frappe.get_doc('POS Settings',name).check_permission('write')
    rows = frappe.get_list('File',filters={'is_folder':0,'is_private':0},
        or_filters=[['file_name','like','%'+ext] for ext in VIDEO_EXTENSIONS],
        fields=['name','file_name','file_url','file_size'],order_by='creation desc',limit_page_length=200)
    return [dict(row) for row in rows if cint(row.file_size) <= MAX_VIDEO_BYTES]


def ensure_upload_limit():
    """Install/migrate hook. Frappe's standard upload ceiling is site-wide."""
    from frappe.core.api.file import get_max_file_size
    effective = get_max_file_size()
    if effective >= MAX_VIDEO_BYTES:
        return {'changed': False, 'max_file_size_bytes': effective}
    import json
    from pathlib import Path
    backup = Path(frappe.get_site_path('private', 'posnext-upload-limit-before.json'))
    backup.parent.mkdir(parents=True, exist_ok=True)
    doc = frappe.get_single('System Settings')
    if not backup.exists():
        with backup.open('x') as stream:
            json.dump({'max_file_size': doc.get('max_file_size')}, stream)
        backup.chmod(0o600)
    doc.max_file_size = 500
    doc.save(ignore_permissions=True)
    frappe.clear_cache(doctype='System Settings')
    return {'changed': True, 'max_file_size_bytes': MAX_VIDEO_BYTES, 'scope': 'site-wide'}


def configure_500mb_uploads():
    """Compatibility administrator command; migration configures this automatically."""
    frappe.only_for('System Manager')
    return ensure_upload_limit()


@frappe.whitelist()
def find_advertising_upload(settings_name, upload_filename, total_file_size):
    """Recover a lost final response without resending an append-mode chunk."""
    import re
    if not re.fullmatch(r'posnext-ad-[a-f0-9]{32}-[a-zA-Z0-9._-]{1,140}', str(upload_filename)):
        frappe.throw(_('Invalid advertising upload identifier.'))
    size = cint(total_file_size)
    if size <= 0 or size > MAX_VIDEO_BYTES:
        frappe.throw(_('Invalid advertising video size.'))
    frappe.get_doc('POS Settings', settings_name).check_permission('write')
    rows = frappe.get_all('File', filters={
        'file_name': upload_filename, 'file_size': size, 'is_private': 0,
        'is_folder': 0, 'owner': frappe.session.user,
        'attached_to_doctype': 'POS Settings', 'attached_to_name': settings_name,
    }, fields=['file_url', 'file_size'], limit_page_length=2)
    return dict(rows[0]) if len(rows) == 1 else None


def cleanup_abandoned_uploads():
    """Remove only POSNext advertising temporary uploads idle for 24 hours."""
    import re
    import time
    from pathlib import Path
    directory = Path(frappe.get_site_path('public', 'files'))
    cutoff = time.time() - 24 * 60 * 60
    if not directory.is_dir():
        return
    for path in directory.glob('.temp-posnext-ad-*'):
        if not re.fullmatch(r'\.temp-posnext-ad-[a-f0-9]{32}-[a-zA-Z0-9._-]{1,140}', path.name):
            continue
        try:
            if not path.is_symlink() and path.is_file() and path.stat().st_mtime < cutoff:
                path.unlink()
        except FileNotFoundError:
            pass
