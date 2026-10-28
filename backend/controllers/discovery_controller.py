"""Public API for the marketplace discovery sections.

Browse page update by Noah Green, 10/17/2026.
"""

import logging
from flask import Blueprint, jsonify, request
from models.discovery_model import get_public_discovery_listings


discovery_bp = Blueprint('discovery_bp', __name__, url_prefix='/api/discover')


@discovery_bp.get('/listings')
def public_listings():
    sort = request.args.get('sort', 'new').strip().lower()
    if sort not in ('new', 'hot'):
        return jsonify({'error': 'sort must be new or hot'}), 400

    try:
        limit = min(48, max(1, int(request.args.get('limit', '24'))))
    except ValueError:
        return jsonify({'error': 'limit must be a number'}), 400

    try:
        return jsonify(get_public_discovery_listings(sort=sort, limit=limit)), 200
    except Exception:
        logging.exception('Could not load discovery listings')
        return jsonify({'error': 'Could not load listings. Please try again.'}), 503
