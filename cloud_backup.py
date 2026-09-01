import os, json, time, traceback
from datetime import datetime

# Lazy import — only if configured
dropbox = None
DbxException = Exception

def _lazy_import():
    global dropbox, DbxException
    if dropbox is None:
        try:
            import dropbox as _dbx
            dropbox = _dbx
            DbxException = _dbx.exceptions.ApiError
        except Exception:
            pass

def _get_token():
    """Get a valid access token via OAuth (auto-refresh)."""
    try:
        from dropbox_oauth import get_access_token
        return get_access_token()
    except Exception:
        # Fallback to old static token
        import database as db
        return db.get_setting('dropbox_token', '')

def _get_token_error():
    """Try to get token and return (token, error_message)."""
    try:
        from dropbox_oauth import get_access_token
        return get_access_token(), None
    except Exception as e:
        # Fallback to old static token
        import database as db
        token = db.get_setting('dropbox_token', '')
        if token:
            return token, None
        return None, str(e)

def _get_dbx():
    _lazy_import()
    token = _get_token()
    if not token or dropbox is None:
        return None
    return dropbox.Dropbox(token)

def _dropbox_path(base_name):
    return f"/westernfx/backups/{base_name}"

def _backup_index():
    """Return list of {name,timestamp,size} stored locally."""
    import database as db
    raw = db.get_setting('backup_index', '[]')
    try:
        return json.loads(raw)
    except Exception:
        return []

def _save_backup_index(index):
    import database as db
    db.set_setting('backup_index', json.dumps(index, default=str))

def backup(upload=True, keep_last=30):
    """Back up the SQLite DB to Dropbox. Returns {success, message, filename}."""
    dbx = _get_dbx()
    if dbx is None:
        return {'success': False, 'message': 'Dropbox not configured. Connect in Settings.'}

    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, 'data', 'westernfx.db')
    if not os.path.exists(db_path):
        return {'success': False, 'message': f'DB file not found: {db_path}'}

    ts = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    filename = f"westernfx_{ts}.db"
    dropbox_path = _dropbox_path(filename)

    try:
        with open(db_path, 'rb') as f:
            file_size = os.path.getsize(db_path)
            # Use upload if < 150MB, otherwise chunked
            if file_size < 150 * 1024 * 1024:
                dbx.files_upload(f.read(), dropbox_path, mode=dropbox.files.WriteMode('overwrite'))
            else:
                # Chunked upload for large files
                CHUNK = 4 * 1024 * 1024
                data = f.read(CHUNK)
                session = dbx.files_upload_session_start(data)
                cursor = dropbox.files.UploadSessionCursor(session_id=session.session_id, offset=len(data))
                commit = dropbox.files.CommitInfo(path=dropbox_path, mode=dropbox.files.WriteMode('overwrite'))
                while True:
                    data = f.read(CHUNK)
                    if not data:
                        break
                    if len(data) < CHUNK:
                        dbx.files_upload_session_finish(data, cursor, commit)
                        break
                    else:
                        dbx.files_upload_session_append_v2(data, cursor)
                        cursor.offset += len(data)

        # Update local index
        index = _backup_index()
        index.insert(0, {
            'name': filename,
            'timestamp': ts,
            'size': file_size,
            'created_at': datetime.now().isoformat()
        })
        # Trim old from index
        if len(index) > keep_last:
            to_delete = index[keep_last:]
            for entry in to_delete:
                try:
                    dbx.files_delete_v2(_dropbox_path(entry['name']))
                except Exception:
                    pass
            index = index[:keep_last]
        _save_backup_index(index)

        import database as db
        db.set_setting('last_backup', datetime.now().isoformat())
        return {'success': True, 'message': f'Backup uploaded: {filename}', 'filename': filename}
    except DbxException as e:
        return {'success': False, 'message': f'Dropbox error: {str(e)}'}
    except Exception as e:
        return {'success': False, 'message': f'Error: {str(e)}'}

def list_backups():
    """Return list of backups from Dropbox directly (syncs local index)."""
    _lazy_import()
    token, err = _get_token_error()
    if err or not token:
        return {'success': False, 'error': err or 'Dropbox not configured. Connect in Settings.'}
    if dropbox is None:
        return {'success': False, 'error': 'Dropbox library not installed.'}

    dbx = dropbox.Dropbox(token)
    try:
        res = dbx.files_list_folder('/westernfx/backups')
        backups = []
        for entry in res.entries:
            if hasattr(entry, 'name') and entry.name.endswith('.db'):
                ts = entry.name.replace('westernfx_', '').replace('.db', '')
                size = getattr(entry, 'size', 0)
                backups.append({
                    'name': entry.name,
                    'timestamp': ts,
                    'size': size,
                    'created_at': getattr(entry, 'client_modified', datetime.now().isoformat())
                })
        backups.sort(key=lambda x: x['timestamp'], reverse=True)
        _save_backup_index(backups)
        return {'success': True, 'backups': backups}
    except DbxException as e:
        return {'success': False, 'error': f'Dropbox API error: {str(e)}'}
    except Exception as e:
        return {'success': False, 'error': f'Error: {str(e)}\n{traceback.format_exc()}'}

def _get_latest_filename():
    """Get latest backup filename from local index."""
    index = _backup_index()
    if not index:
        return None
    return index[0]['name']

def restore(filename=None):
    """Restore DB from Dropbox. Returns {success, message}."""
    dbx = _get_dbx()
    if dbx is None:
        return {'success': False, 'message': 'Dropbox not configured. Connect in Settings.'}

    if filename is None:
        filename = _get_latest_filename()
        if filename is None:
            return {'success': False, 'message': 'No backups found in index.'}

    dropbox_path = _dropbox_path(filename)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, 'data', 'westernfx.db')
    backup_local = db_path + '.backup.' + datetime.now().strftime('%Y%m%d_%H%M%S')

    try:
        # Download file
        _, res = dbx.files_download(dropbox_path)
        # Backup current DB first
        if os.path.exists(db_path):
            import shutil
            shutil.copy2(db_path, backup_local)
        # Write restored data
        with open(db_path, 'wb') as f:
            f.write(res.content)

        # Ensure all required tables exist (e.g., auth_ips on restored old DB)
        from database import init_db
        init_db()

        return {'success': True, 'message': f'Restored from {filename}. Local backup saved as {os.path.basename(backup_local)}'}
    except DbxException as e:
        return {'success': False, 'message': f'Dropbox error: {str(e)}'}
    except Exception as e:
        return {'success': False, 'message': f'Error: {str(e)}'}

def get_status():
    """Return backup status."""
    try:
        from dropbox_oauth import test_connection
        result = test_connection()
        configured = True
        connected = result.get('connected', False)
        error = result.get('error', '')
    except Exception:
        # Fallback to old static token check
        import database as db
        token = db.get_setting('dropbox_token', '')
        if not token:
            return {'success': True, 'configured': False, 'message': 'Dropbox not connected. Click Connect in Settings.'}
        configured = True
        connected = False
        error = "Old token mode"

    last = None
    try:
        import database as db
        last = db.get_setting('last_backup')
    except Exception:
        pass

    return {
        'success': True,
        'configured': configured,
        'connected': connected,
        'last_backup': last,
        'message': f"Last backup: {last or 'Never'}"
    }
