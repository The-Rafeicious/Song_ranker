"""Authenticated, browser-bound review/apply endpoints for tag-only catalogue work."""
import os
from flask import jsonify,request
from itsdangerous import URLSafeTimedSerializer,BadData

from songranker.services import (app, admin_required, get_db_connection, create_database_backup)
from songranker.developer.catalog_sources import owner
from songranker.developer.tag_operations import (canonical_proposal, plan, apply_memberships)


def signer():return URLSafeTimedSerializer(app.secret_key,salt='catalog-tag-review-v1')


@app.route('/api/dev/tags/review',methods=['POST'])
@admin_required
def review_tags():
    conn=get_db_connection()
    try:
        conn.execute('BEGIN')
        change=canonical_proposal(conn,request.get_json(silent=True));review=plan(conn,change)
        token=signer().dumps(dict(owner=owner(),change=change,before=review['before_hash'],after=review['after_hash']))
        return jsonify(**{k:v for k,v in review.items() if not k.endswith('_hash')},review_token=token)
    except ValueError as error:return jsonify(message=str(error)),400
    finally:conn.close()


@app.route('/api/dev/tags/apply',methods=['POST'])
@admin_required
def apply_tags():
    data=request.get_json(silent=True)
    if not isinstance(data,dict) or not isinstance(data.get('review_token'),str) or len(data['review_token'])>250000:
        return jsonify(message='Review the tag changes before saving.'),400
    try:verified=signer().loads(data['review_token'],max_age=86400)
    except BadData:return jsonify(message='This tag review expired or changed. Review again.'),400
    if verified.get('owner')!=owner():return jsonify(message='Review tags in this browser before saving.'),400
    conn=get_db_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        try:review=plan(conn,verified['change'])
        except ValueError as error:return jsonify(message=str(error)),409
        if review['before_hash']==verified['after']:
            return jsonify(status='success',already_matches=True,updated=0,added_links=0,removed_links=0,created_tags=[],backup=None,
                message='Tags already match this review. Nothing changed.')
        if review['before_hash']!=verified['before']:
            return jsonify(message='Songs or tags changed since this review. Review again before saving.'),409
        created=apply_memberships(conn,review)
        response=jsonify(status='success',already_matches=False,updated=review['changed_songs'],added_links=review['added_links'],
            removed_links=review['removed_links'],created_tags=created,backup=None,
            message=f"Updated tags on {review['changed_songs']} songs.")
        conn.commit();return response
    except Exception:
        conn.rollback();app.logger.exception('Reviewed tag save failed')
        return jsonify(message='Tags could not be saved. No tag changes were applied. Check database health and try again.'),500
    finally:conn.close()
