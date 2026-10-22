"""Bounded, authenticated raw SQLite inspection. Never accepts executable SQL."""
import base64
import hashlib
import json
import sqlite3
import time
from flask import jsonify,request
from songranker import services
from songranker.services import app,admin_required
from songranker.storage.database_io import readonly,quote
from songranker.developer.dev_system import signed,unpack


def integer(name,default,maximum):
    value=request.args.get(name,str(default))
    if not value.isascii() or not value.isdecimal() or int(value)>maximum:raise ValueError('Invalid '+name+'.')
    return int(value)


def object_info(conn,name):
    obj=conn.execute("SELECT name,type,sql FROM sqlite_master WHERE name=? AND type IN ('table','view')",(name,)).fetchone()
    if not obj:raise ValueError('Choose a current table or view.')
    columns=[dict(r) for r in conn.execute('PRAGMA table_xinfo('+quote(name)+')')]
    # PK order is stable for ordinary and WITHOUT ROWID tables; views have no row identity.
    keys=sorted((c['pk'],c['name']) for c in columns if c['pk'])
    order=' ORDER BY '+','.join(quote(n) for _,n in keys) if keys else ''
    return dict(obj),columns,order


def row_hash(row):
    return hashlib.sha256(json.dumps([(type(v).__name__,base64.b64encode(v).decode() if isinstance(v,bytes) else v) for v in row],ensure_ascii=True,separators=(',',':')).encode()).hexdigest()


def cell(value,start=0,limit=256):
    if value is None:return dict(type='null',value=None,total=0,truncated=False)
    if isinstance(value,bytes):
        return dict(type='blob',value=base64.b64encode(value[start:start+limit]).decode(),total=len(value),truncated=start+limit<len(value),unit='bytes',encoding='base64')
    kind='integer' if isinstance(value,int) else 'real' if isinstance(value,float) else 'text'
    text=str(value)
    return dict(type=kind,value=text[start:start+limit],total=len(text),truncated=start+limit<len(text),unit='characters')


def deadline(conn):
    end=time.monotonic()+3
    conn.execute('PRAGMA busy_timeout=1000')
    conn.execute('PRAGMA query_only=ON')
    conn.set_progress_handler(lambda:int(time.monotonic()>end),1000)
    conn.execute('BEGIN')


@app.get('/api/dev/database/inspect')
@admin_required
def inspect_object():
    try:
        name=request.args.get('name','');offset=integer('offset',0,10000000);limit=integer('limit',25,50)
        if not limit:raise ValueError('Choose a positive page size.')
        with readonly(services.DB_NAME) as conn:
            deadline(conn);obj,columns,order=object_info(conn,name)
            limit=min(limit,max(1,1000//max(1,len(columns))))
            total=conn.execute('SELECT COUNT(*) FROM '+quote(name)).fetchone()[0]
            rows=conn.execute('SELECT '+','.join(quote(c['name']) for c in columns)+' FROM '+quote(name)+order+' LIMIT ? OFFSET ?',(limit,offset)).fetchall()
            result=[]
            for i,row in enumerate(rows):
                values=list(row);token=signed('db_row',name=name,offset=offset+i,digest=row_hash(values))
                result.append(dict(cells=[cell(v) for v in values],review_token=token))
            return jsonify(object=obj,columns=columns,foreign_keys=[dict(r) for r in conn.execute('PRAGMA foreign_key_list('+quote(name)+')')],
                indexes=[dict(r) for r in conn.execute('PRAGMA index_list('+quote(name)+')')],rows=result,total=total,offset=offset,limit=limit)
    except ValueError as error:return jsonify(message=str(error)),400
    except (sqlite3.Error,OSError):return jsonify(message='This object could not be read within the inspection limit. No data was changed.'),422


@app.get('/api/dev/database/cell')
@admin_required
def inspect_cell():
    try:
        reviewed=unpack(request.args.get('review_token'),'db_row');column=integer('column',0,1999);start=integer('start',0,1000000000)
        with readonly(services.DB_NAME) as conn:
            deadline(conn);_,columns,order=object_info(conn,reviewed['name'])
            if column>=len(columns):raise ValueError('Choose a current column.')
            row=conn.execute('SELECT '+','.join(quote(c['name']) for c in columns)+' FROM '+quote(reviewed['name'])+order+' LIMIT 1 OFFSET ?',(reviewed['offset'],)).fetchone()
            if row is None or row_hash(list(row))!=reviewed['digest']:return jsonify(message='This row changed. Refresh the table before inspecting its values.'),409
            return jsonify(**cell(row[column],start,4096),start=start,limit=4096,column=columns[column]['name'])
    except ValueError as error:return jsonify(message=str(error)),400
    except (sqlite3.Error,OSError):return jsonify(message='This value could not be read. No data was changed.'),422
