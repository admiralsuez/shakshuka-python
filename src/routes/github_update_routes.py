from flask import Blueprint, jsonify, request
import logging
import os

from src.exceptions import DatabaseError, ValidationError
from src.routes.api_utils import get_json_object, register_api_error_handlers

logger = logging.getLogger(__name__)

github_update_bp = Blueprint("github_update", __name__, url_prefix="/api/github")

register_api_error_handlers(github_update_bp)

_get_app_version_func = None
_is_newer_version_func = None
_repo_owner = None
_repo_name = None


def init_github_update_routes(get_app_version_func, is_newer_version_func, repo_owner: str, repo_name: str):
    global _get_app_version_func, _is_newer_version_func, _repo_owner, _repo_name
    _get_app_version_func = get_app_version_func
    _is_newer_version_func = is_newer_version_func
    _repo_owner = repo_owner
    _repo_name = repo_name


@github_update_bp.route('/check-update', methods=['POST'])
def check_github_update():
    """Check for updates from GitHub releases"""
    try:
        import requests
    except Exception as e:
        raise DatabaseError(message='requests module not available', cause=e)

    data = get_json_object(required=False)

    branch = data.get('branch', 'main')
    if not isinstance(branch, str) or branch.strip() == "":
        raise ValidationError(message='branch must be a non-empty string')

    repo_owner = _repo_owner
    repo_name = _repo_name
    if not isinstance(repo_owner, str) or not repo_owner.strip() or not isinstance(repo_name, str) or not repo_name.strip():
        raise DatabaseError(message='GitHub repo not configured')

    if branch == 'main':
        url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/releases/latest"
        params = None
    else:
        url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/releases"
        params = {'per_page': 1}

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
    except Exception as e:
        raise DatabaseError(message='Failed to connect to GitHub', cause=e)

    try:
        if branch == 'main':
            release_data = response.json()
        else:
            releases = response.json()
            if not releases:
                return jsonify({'update_available': False, 'message': 'No releases found for this branch'}), 200
            release_data = releases[0]
    except Exception as e:
        raise DatabaseError(message='Invalid GitHub response', cause=e)

    if not _get_app_version_func or not _is_newer_version_func:
        raise DatabaseError(message='GitHub update routes not initialized')

    current_version = _get_app_version_func()
    latest_version = str(release_data.get('tag_name') or '').lstrip('v')
    if not latest_version:
        raise DatabaseError(message='GitHub release missing tag_name')
    update_available = bool(_is_newer_version_func(latest_version, current_version))

    asset_url = None
    asset_size = 0
    for asset in release_data.get('assets', []) or []:
        name = str(asset.get('name', '')).lower()
        if name.endswith('.exe') and ('setup' in name or 'installer' in name):
            asset_url = asset.get('browser_download_url')
            asset_size = int(asset.get('size', 0) or 0)
            break

    if not asset_url:
        assets = release_data.get('assets', []) or []
        if assets:
            asset_url = assets[0].get('browser_download_url')
            asset_size = int(assets[0].get('size', 0) or 0)

    return jsonify(
        {
            'update_available': update_available,
            'current_version': current_version,
            'latest_version': latest_version,
            'release_info': {
                'tag_name': release_data.get('tag_name'),
                'name': release_data.get('name'),
                'body': release_data.get('body'),
                'published_at': release_data.get('published_at'),
                'download_url': asset_url,
                'file_size': asset_size
            }
        }
    ), 200


@github_update_bp.route('/download-update', methods=['POST'])
def download_github_update():
    """Download and prepare update from GitHub."""
    try:
        import requests
        import tempfile
    except Exception as e:
        raise DatabaseError(message='requests module not available', cause=e)

    data = get_json_object(required=False)

    branch = data.get('branch', 'main')
    if not isinstance(branch, str) or branch.strip() == "":
        raise ValidationError(message='branch must be a non-empty string')

    repo_owner = _repo_owner
    repo_name = _repo_name
    if not isinstance(repo_owner, str) or not repo_owner.strip() or not isinstance(repo_name, str) or not repo_name.strip():
        raise DatabaseError(message='GitHub repo not configured')

    if branch == 'main':
        url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/releases/latest"
        params = None
    else:
        url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/releases"
        params = {'per_page': 1}

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
    except Exception as e:
        raise DatabaseError(message='Failed to connect to GitHub', cause=e)

    try:
        if branch == 'main':
            release_data = response.json()
        else:
            releases = response.json()
            if not releases:
                return jsonify({'success': False, 'error': 'No releases found for this branch'}), 404
            release_data = releases[0]
    except Exception as e:
        raise DatabaseError(message='Invalid GitHub response', cause=e)

    installer_url = None
    installer_size = 0
    installer_name = None
    for asset in release_data.get('assets', []) or []:
        name = str(asset.get('name', ''))
        if name.lower().endswith('.exe') and 'setup' in name.lower():
            installer_url = asset.get('browser_download_url')
            installer_size = int(asset.get('size', 0) or 0)
            installer_name = name
            break

    if not installer_url:
        return jsonify({'success': False, 'error': 'No Windows installer found in release'}), 404

    try:
        home_dir = os.path.expanduser('~')
        downloads_dir = os.path.join(home_dir, 'Downloads')
        if not os.path.isdir(downloads_dir):
            downloads_dir = tempfile.gettempdir()
    except Exception:  # noqa: broad-except
        downloads_dir = tempfile.gettempdir()

    os.makedirs(downloads_dir, exist_ok=True)

    if not installer_name:
        tag = str(release_data.get('tag_name') or 'latest').lstrip('v')
        installer_name = f'Shakshuka-Setup-{tag}.exe'

    installer_path = os.path.join(downloads_dir, installer_name)

    logger.info(f"Downloading update from: {installer_url} to {installer_path}")
    try:
        download_response = requests.get(installer_url, stream=True, timeout=30)
        download_response.raise_for_status()
    except Exception as e:
        raise DatabaseError(message='Failed to download installer', cause=e)

    with open(installer_path, 'wb') as f:
        for chunk in download_response.iter_content(chunk_size=8192):
            if not chunk:
                continue
            f.write(chunk)

    logger.info(f"Downloaded installer to: {installer_path}")

    return jsonify(
        {
            'success': True,
            'message': 'Update downloaded successfully',
            'installer_size': installer_size,
            'installer_path': installer_path,
            'release_info': {
                'tag_name': release_data.get('tag_name'),
                'name': release_data.get('name'),
                'body': release_data.get('body'),
            }
        }
    ), 200
