from flask import Blueprint, jsonify, request, session
import logging
import secrets
from datetime import datetime

logger = logging.getLogger(__name__)

pin_bp = Blueprint("pin", __name__, url_prefix="/api/pin")

_app_context = None


def init_pin_routes(app_context):
    global _app_context
    _app_context = app_context


@pin_bp.route("/status", methods=["GET"])
def get_pin_status():
    """Check if PIN is setup and get cooldown status"""
    try:
        if not _app_context or not _app_context.pin_manager:
            return jsonify({'error': 'PIN manager not initialized'}), 500

        is_setup = _app_context.pin_manager.is_setup_complete()
        in_cooldown, seconds_remaining = _app_context.pin_manager.is_in_cooldown()

        response = {
            'setup_complete': is_setup,
            'in_cooldown': in_cooldown,
            'seconds_remaining': seconds_remaining,
            'session_valid': _app_context.pin_manager.is_session_valid() if is_setup else False
        }

        if is_setup:
            response['last_login'] = _app_context.pin_manager.get_last_login()
            response['failed_attempts'] = _app_context.pin_manager.get_failed_attempts()
            response['remembered'] = _app_context.pin_manager.is_remembered()
            response['session_expires'] = _app_context.pin_manager.get_session_expiry()

        return jsonify(response)
    except Exception as e:
        logger.error(f"Error checking PIN status: {e}")
        return jsonify({'error': 'Failed to check PIN status'}), 500


@pin_bp.route("/setup", methods=["POST"])
def setup_pin():
    """Setup new PIN"""
    try:
        if not _app_context or not _app_context.pin_manager:
            return jsonify({'error': 'PIN manager not initialized'}), 500

        data = request.json
        if data is None or not isinstance(data, dict):
            return jsonify({'error': 'Request must contain JSON object'}), 400

        pin = data.get('pin', '')
        confirm_pin = data.get('confirm_pin', '')
        recovery_questions = data.get('recovery_questions', [])

        if not isinstance(recovery_questions, list):
            return jsonify({'error': 'recovery_questions must be a list'}), 400

        success, message = _app_context.pin_manager.setup_pin(pin, confirm_pin, recovery_questions)

        if success:
            session_token = secrets.token_urlsafe(32)
            session['authenticated'] = True
            session['session_token'] = session_token
            session['auth_time'] = datetime.now().isoformat()

            return jsonify({
                'success': True,
                'message': message,
                'session_token': session_token
            })

        return jsonify({'error': message}), 400

    except Exception as e:
        logger.error(f"Error setting up PIN: {e}")
        return jsonify({'error': 'Failed to setup PIN'}), 500


@pin_bp.route("/verify", methods=["POST"])
def verify_pin():
    """Verify PIN and login"""
    try:
        if not _app_context or not _app_context.pin_manager:
            return jsonify({'error': 'PIN manager not initialized'}), 500

        data = request.json
        if data is None or not isinstance(data, dict):
            return jsonify({'error': 'Request must contain JSON object'}), 400

        pin = data.get('pin', '')
        remember = data.get('remember', False)

        if not isinstance(remember, bool):
            return jsonify({'error': 'remember must be boolean'}), 400

        success, message, attempts_remaining = _app_context.pin_manager.verify_pin(pin, remember)

        if success:
            session_token = secrets.token_urlsafe(32)
            session['authenticated'] = True
            session['session_token'] = session_token
            session['auth_time'] = datetime.now().isoformat()

            return jsonify({
                'success': True,
                'message': message,
                'session_token': session_token,
                'remembered': remember
            })

        return jsonify({
            'error': message,
            'attempts_remaining': attempts_remaining
        }), 401

    except Exception as e:
        logger.error(f"Error verifying PIN: {e}")
        return jsonify({'error': 'Failed to verify PIN'}), 500


@pin_bp.route("/reset", methods=["POST"])
def reset_pin():
    """Reset PIN (forgot PIN recovery)"""
    try:
        if not _app_context or not _app_context.pin_manager:
            return jsonify({'error': 'PIN manager not initialized'}), 500

        data = request.json
        if data is None or not isinstance(data, dict):
            return jsonify({'error': 'Request must contain JSON object'}), 400

        new_pin = data.get('new_pin', '')
        confirm_pin = data.get('confirm_pin', '')

        success, message = _app_context.pin_manager.reset_pin(new_pin, confirm_pin)

        if success:
            session_token = secrets.token_urlsafe(32)
            session['authenticated'] = True
            session['session_token'] = session_token
            session['auth_time'] = datetime.now().isoformat()

            return jsonify({
                'success': True,
                'message': message,
                'session_token': session_token
            })

        return jsonify({'error': message}), 400

    except Exception as e:
        logger.error(f"Error resetting PIN: {e}")
        return jsonify({'error': 'Failed to reset PIN'}), 500


@pin_bp.route("/logout", methods=["POST"])
def logout():
    """Logout and clear session"""
    try:
        if _app_context and _app_context.pin_manager:
            _app_context.pin_manager.logout()

        session.clear()
        return jsonify({'success': True, 'message': 'Logged out successfully'})
    except Exception as e:
        logger.error(f"Error during logout: {e}")
        return jsonify({'error': 'Logout failed'}), 500
