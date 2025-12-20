from flask import Blueprint, jsonify, request
import logging
import os

logger = logging.getLogger(__name__)

github_update_bp = Blueprint("github_update", __name__, url_prefix="/api/github")

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

        data = request.get_json() or {}
        if not isinstance(data, dict):
            return jsonify({'error': 'Request must contain JSON object'}), 400

        branch = data.get('branch', 'main')
        if not isinstance(branch, str) or branch.strip() == "":
            return jsonify({'error': 'branch must be a non-empty string'}), 400

        repo_owner = _repo_owner
        repo_name = _repo_name

        if branch == 'main':
            url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/releases/latest"
            params = None
        else:
            url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/releases"
            params = {'per_page': 1}
            if branch in ('testing', 'development'):
                params['prerelease'] = True

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()

        if branch == 'main':
            release_data = response.json()
        else:
            releases = response.json()
            if not releases:
                return jsonify({'update_available': False, 'message': 'No releases found for this branch'})
            release_data = releases[0]

        current_version = _get_app_version_func() if _get_app_version_func else '1.0.0'
        latest_version = str(release_data['tag_name']).lstrip('v')
        update_available = _is_newer_version_func(latest_version, current_version) if _is_newer_version_func else False

        asset_url = None
        asset_size = 0
        for asset in release_data.get('assets', []):
            name = asset.get('name', '').lower()
            if name.endswith('.exe') and ('setup' in name or 'installer' in name):
                asset_url = asset.get('browser_download_url')
                asset_size = int(asset.get('size', 0))
                break

        if not asset_url:
            assets = release_data.get('assets', [])
            if assets:
                asset_url = assets[0].get('browser_download_url')
                asset_size = int(assets[0].get('size', 0))

        return jsonify({
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
        })

    except Exception as e:
        logger.error(f"GitHub API error: {e}")
        return jsonify({'error': 'Failed to connect to GitHub', 'update_available': False}), 500


@github_update_bp.route('/download-update', methods=['POST'])
def download_github_update():
    """Download and prepare update from GitHub."""
    try:
        import requests
        import tempfile

        data = request.get_json() or {}
        if not isinstance(data, dict):
            return jsonify({'error': 'Request must contain JSON object'}), 400

        branch = data.get('branch', 'main')
        if not isinstance(branch, str) or branch.strip() == "":
            return jsonify({'error': 'branch must be a non-empty string'}), 400

        repo_owner = _repo_owner
        repo_name = _repo_name

        if branch == 'main':
            url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/releases/latest"
            params = None
        else:
            url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/releases"
            params = {'per_page': 1}
            if branch in ('testing', 'development'):
                params['prerelease'] = True

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()

        if branch == 'main':
            release_data = response.json()
        else:
            releases = response.json()
            if not releases:
                return jsonify({'error': 'No releases found for this branch'}), 404
            release_data = releases[0]

        installer_url = None
        installer_size = 0
        installer_name = None
        for asset in release_data.get('assets', []):
            name = asset.get('name', '')
            if name.lower().endswith('.exe') and 'setup' in name.lower():
                installer_url = asset.get('browser_download_url')
                installer_size = int(asset.get('size', 0) or 0)
                installer_name = name
                break

        if not installer_url:
            return jsonify({'error': 'No Windows installer found in release'}), 404

        try:
            home_dir = os.path.expanduser('~')
            downloads_dir = os.path.join(home_dir, 'Downloads')
            if not os.path.isdir(downloads_dir):
                downloads_dir = tempfile.gettempdir()
        except Exception:
            downloads_dir = tempfile.gettempdir()

        os.makedirs(downloads_dir, exist_ok=True)

        if not installer_name:
            tag = str(release_data.get('tag_name') or 'latest').lstrip('v')
            installer_name = f'Shakshuka-Setup-{tag}.exe'

        installer_path = os.path.join(downloads_dir, installer_name)

        logger.info(f"Downloading update from: {installer_url} to {installer_path}")
        download_response = requests.get(installer_url, stream=True, timeout=30)
        download_response.raise_for_status()

        with open(installer_path, 'wb') as f:
            for chunk in download_response.iter_content(chunk_size=8192):
                if not chunk:
                    continue
                f.write(chunk)

        logger.info(f"Downloaded installer to: {installer_path}")

        return jsonify({
            'success': True,
            'message': 'Update downloaded successfully',
            'installer_size': installer_size,
            'installer_path': installer_path,
            'release_info': {
                'tag_name': release_data.get('tag_name'),
                'name': release_data.get('name'),
                'body': release_data.get('body'),
            }
        })

    except Exception as e:
        logger.error(f"GitHub download error: {e}")
        return jsonify({'error': 'Failed to download update'}), 500
