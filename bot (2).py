import os, sqlite3, secrets, json, asyncio, re
from datetime import datetime
from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, BotCommand, BotCommandScopeDefault, BotCommandScopeChat, MessageEntity
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

load_dotenv(); TOKEN=os.getenv('BOT_TOKEN')
if not TOKEN: raise RuntimeError('BOT_TOKEN belum diset di environment variable')
DEFAULT_ADMIN_IDS={1137740036,1779151962,1943239073,7186342193}; OWNER_ID=1137740036
CHANNEL_ID=-1001967813918; FREE_GROUP_ID=-1002228292417; MEMBERSHIP_GROUP_ID=-1002115664800
DEFAULT_CHANNEL_LINK='https://t.me/Nakahoshi'; DEFAULT_FREE_GROUP_LINK='https://t.me/+lYiuGXIVy1JkYWE9'; DEFAULT_PAYMENT_LINK='https://t.me/nakanosqbot?start=NakaFileBOT'; DEFAULT_OWNER_LINK='https://t.me/seiizn'; DB_NAME='files.db'
DEFAULT_START_TEXT='''╭━━━━━━━━━━━━━━━━━━━━╮
       ✦ NAKAHOSHI ✦
      FILE SHARE BOT
╰━━━━━━━━━━━━━━━━━━━━╯

🤖 BOT KHUSUS FILE SHARE
   NON-MEMBERSHIP USER

Jika Anda sudah bergabung ke Membership Nakahoshi, silakan langsung menikmati konten Membership.

🎬 @Nakahoshi

━━━━━━━━━━━━━━━━━━━━

Belum menjadi member?

⭐ Membership Nakahoshi
💰 Rp15.000 / 30 Hari

Dapatkan akses Membership dan nikmati konten lengkap.

👇 Pilih akses Anda:'''
DEFAULT_FSUB_TEXT='UNTUK FREE USER, SILAHKAN BERGABUNG TERLEBIH DAHULU KE GRUP DAN CHANNEL UTAMA KAMI UNTUK MENDAPATKAN FILE!!\n\nSETELAH BERGABUNG KE CHANNEL DAN GRUP, SILAHKAN TEKAN TOMBOL 🔄 CEK AKSES DI BAWAH UNTUK MENDAPATKAN FILE.\n\n━━━━━━━━━━━━━━━━━━━━\n\n💎 MEMBERSHIP NAKAHOSHI\n\nBosan menggunakan bot file?\nNggak perlu ribet cari file atau join sana-sini.\nLangsung saja tekan tombol ⭐ JOIN MEMBERSHIP di bawah!'
DEFAULT_BANNED_TEXT='🚫 AKUN KAMU TELAH DI-BANNED.\n\nJika merasa ini kesalahan, silakan hubungi Customer Service.'; DEFAULT_DENIED_TEXT='🚫 COMMAND KHUSUS ADMIN.\n\nKamu tidak memiliki izin untuk menggunakan command ini.'
DEFAULT_NOT_FOUND_TEXT='❌ File tidak ditemukan atau sudah tidak tersedia.'; DEFAULT_INVALID_LINK_TEXT='❌ Link file tidak valid.'; DEFAULT_ACCESS_OK_TEXT='✅ AKSES OK\n\n📤 File sedang dikirim...'; DEFAULT_DELETE_NOTICE='⚠️ FILE INI AKAN DIHAPUS OTOMATIS DALAM {minutes} MENIT.'
DEFAULT_CS_TEXT='🛠️ CUSTOMER SERVICE NAKAHOSHI\n\nJika terdapat masalah pada file, akses, atau akun, silakan hubungi admin kami.'; DEFAULT_UNBAN_TEXT='🚫 Akun kamu sedang dibanned.\n\nSilakan ajukan permintaan unban kepada admin melalui tombol di bawah.'; DEFAULT_MAINTENANCE_TEXT='🔧 NAKAHOSHI SEDANG DALAM PEMELIHARAAN.\n\nSilakan coba kembali nanti.'
admin_sessions={}; pending_batches={}

def db():
    c=sqlite3.connect(DB_NAME,timeout=30); c.row_factory=sqlite3.Row; return c

def ensure_column(c,t,col,definition):
    if col not in {r[1] for r in c.execute(f'PRAGMA table_info({t})').fetchall()}: c.execute(f'ALTER TABLE {t} ADD COLUMN {col} {definition}')

def init_db():
    c=db();q=c.cursor();q.execute('CREATE TABLE IF NOT EXISTS files (code TEXT PRIMARY KEY,file_id TEXT NOT NULL,file_type TEXT NOT NULL,caption TEXT)');q.execute('CREATE TABLE IF NOT EXISTS batches (code TEXT PRIMARY KEY,created_by INTEGER,created_at TEXT)');q.execute('CREATE TABLE IF NOT EXISTS batch_items (id INTEGER PRIMARY KEY AUTOINCREMENT,batch_code TEXT NOT NULL,file_id TEXT NOT NULL,file_type TEXT NOT NULL,caption TEXT)');q.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY,username TEXT,first_name TEXT,first_seen TEXT,last_seen TEXT)');q.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY,value TEXT)');q.execute('CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY,added_at TEXT,added_by INTEGER)');q.execute('CREATE TABLE IF NOT EXISTS banned_users (user_id INTEGER PRIMARY KEY,reason TEXT,banned_at TEXT,banned_by INTEGER)');q.execute('CREATE TABLE IF NOT EXISTS user_commands (command TEXT PRIMARY KEY,description TEXT,config TEXT NOT NULL,enabled INTEGER NOT NULL DEFAULT 1)');ensure_column(c,'files','caption_entities','TEXT');ensure_column(c,'batch_items','caption_entities','TEXT')
    def cfg(t,e=None,m='',mt='',b=None):return json.dumps({'text':t,'entities':e or [],'media_id':m,'media_type':mt,'buttons':b or []},ensure_ascii=False)
    defaults={'start_text':DEFAULT_START_TEXT,'start_media':'','start_media_type':'','start_entities':'[]','start_config':cfg(DEFAULT_START_TEXT,b=[['⭐ JOIN MEMBERSHIP','url',DEFAULT_PAYMENT_LINK],['📢 JOIN CHANNEL','url',DEFAULT_CHANNEL_LINK],['👥 JOIN GROUP','url',DEFAULT_FREE_GROUP_LINK],['👤 OWNER BOT','url',DEFAULT_OWNER_LINK]]),'fsub_config':cfg(DEFAULT_FSUB_TEXT,b=[['📢 JOIN CHANNEL','url',DEFAULT_CHANNEL_LINK],['👥 JOIN GROUP','url',DEFAULT_FREE_GROUP_LINK],['🔄 CEK AKSES','check',''],['⭐ JOIN MEMBERSHIP','url',DEFAULT_PAYMENT_LINK]]),'membership_price':'Rp15.000 / 30 Hari','channel_link':DEFAULT_CHANNEL_LINK,'free_group_link':DEFAULT_FREE_GROUP_LINK,'payment_link':DEFAULT_PAYMENT_LINK,'owner_link':DEFAULT_OWNER_LINK,'cs_link':DEFAULT_OWNER_LINK,'protect_content':'1','auto_delete_enabled':'0','auto_delete_minutes':'10','auto_delete_notice':cfg(DEFAULT_DELETE_NOTICE),'banned_message':cfg(DEFAULT_BANNED_TEXT),'denied_message':cfg(DEFAULT_DENIED_TEXT),'not_found_message':cfg(DEFAULT_NOT_FOUND_TEXT),'invalid_link_message':cfg(DEFAULT_INVALID_LINK_TEXT),'access_ok_message':cfg(DEFAULT_ACCESS_OK_TEXT),'cs_config':cfg(DEFAULT_CS_TEXT,b=[['👤 HUBUNGI ADMIN','url',DEFAULT_OWNER_LINK]]),'unban_config':cfg(DEFAULT_UNBAN_TEXT,b=[['📝 AJUKAN UNBAN','url',DEFAULT_OWNER_LINK]]),'maintenance_config':cfg(DEFAULT_MAINTENANCE_TEXT),'maintenance':'0'}
    for k,v in defaults.items():q.execute('INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)',(k,v))
    for uid in DEFAULT_ADMIN_IDS:q.execute('INSERT OR IGNORE INTO admins(user_id,added_at,added_by) VALUES(?,?,?)',(uid,datetime.now().isoformat(timespec='seconds'),OWNER_ID))
    commands={'peraturan':('Peraturan Nakahoshi',cfg('📜 PERATURAN NAKAHOSHI\n\nSilakan isi peraturan Nakahoshi melalui Admin Panel.')),'unbanned':('Pengajuan unban akun',cfg(DEFAULT_UNBAN_TEXT,b=[['📝 AJUKAN UNBAN','url',DEFAULT_OWNER_LINK]])),'joinvip':('Membership Nakahoshi',cfg('⭐ JOIN VIP\n\nCuma Rp15.000 / 30 Hari. Murah banget 😝',b=[['⭐ JOIN MEMBERSHIP','url',DEFAULT_PAYMENT_LINK]])),'listchannel':('List channel Nakahoshi',cfg('📚 LIST CHANNEL NAKAHOSHI\n\nSilakan pilih channel/folder yang ingin kamu buka 👇')),'customerservice':('Hubungi Customer Service',cfg(DEFAULT_CS_TEXT,b=[['👤 HUBUNGI ADMIN','url',DEFAULT_OWNER_LINK]]))}
    for cmd,(desc,conf) in commands.items():q.execute('INSERT OR IGNORE INTO user_commands(command,description,config,enabled) VALUES(?,?,?,1)',(cmd,desc,conf))
    c.commit();c.close()

def get_setting(k):
    c=db();r=c.execute('SELECT value FROM settings WHERE key=?',(k,)).fetchone();c.close();return r['value'] if r else ''
def set_setting(k,v):
    c=db();c.execute('INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)',(k,v));c.commit();c.close()
def admins():
    c=db();r={int(x['user_id']) for x in c.execute('SELECT user_id FROM admins')};c.close();r.add(OWNER_ID);return r
def is_admin(uid):return uid in admins()
def is_banned(uid):
    c=db();r=c.execute('SELECT 1 FROM banned_users WHERE user_id=?',(uid,)).fetchone();c.close();return bool(r) and uid not in admins()
def save_user(u):
    if not u:return
    n=datetime.now().isoformat(timespec='seconds');c=db();c.execute('''INSERT INTO users(user_id,username,first_name,first_seen,last_seen) VALUES(?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET username=excluded.username,first_name=excluded.first_name,last_seen=excluded.last_seen''',(u.id,u.username or '',u.first_name or '',n,n));c.commit();c.close()
def ser_entities(es):
    out=[]
    for e in es or []:
        d={'type':e.type,'offset':e.offset,'length':e.length}
        for k in ('url','language','custom_emoji_id'):
            v=getattr(e,k,None)
            if v is not None:d[k]=v
        out.append(d)
    return out
def deser_entities(raw):
    try:data=json.loads(raw or '[]') if isinstance(raw,str) else (raw or [])
    except:return []
    out=[]
    for d in data:
        try:out.append(MessageEntity(**{k:d[k] for k in ('type','offset','length','url','language','custom_emoji_id') if k in d}))
        except:pass
    return out
def get_cfg(k):
    try:return json.loads(get_setting(k) or '{}')
    except:return {'text':'','entities':[],'media_id':'','media_type':'','buttons':[]}
def set_cfg(k,c):set_setting(k,json.dumps(c,ensure_ascii=False))
def command_row(cmd):
    c=db();r=c.execute('SELECT * FROM user_commands WHERE command=?',(cmd,)).fetchone();c.close();return r
def make_code(p):return p+'_'+secrets.token_urlsafe(10)
def create_file(fid,typ,cap,es):
    x=make_code('F');c=db();c.execute('INSERT INTO files(code,file_id,file_type,caption,caption_entities) VALUES(?,?,?,?,?)',(x,fid,typ,cap or '',json.dumps(ser_entities(es),ensure_ascii=False)));c.commit();c.close();return x
def create_batch(uid,items):
    x=make_code('B');c=db();c.execute('INSERT INTO batches(code,created_by,created_at) VALUES(?,?,?)',(x,uid,datetime.now().isoformat(timespec='seconds')));c.executemany('INSERT INTO batch_items(batch_code,file_id,file_type,caption,caption_entities) VALUES(?,?,?,?,?)',[(x,*i[:2],i[2] or '',json.dumps(ser_entities(i[3]),ensure_ascii=False)) for i in items]);c.commit();c.close();return x
def get_file(x):
    c=db();r=c.execute('SELECT * FROM files WHERE code=?',(x,)).fetchone();c.close();return r
def get_batch(x):
    c=db();r=c.execute('SELECT * FROM batch_items WHERE batch_code=? ORDER BY id',(x,)).fetchall();c.close();return r

def make_button(b,code=None):
    if not isinstance(b,(list,tuple)) or len(b)<2:return None
    label,kind=b[0],b[1];val=b[2] if len(b)>2 else '';style=b[3] if len(b)>3 else None;icon=b[4] if len(b)>4 else None;kw={'callback_data':f'check:{code}'} if kind=='check' and code else ({'url':val} if kind=='url' and val else None)
    if not kw:return None
    if style in {'primary','success','danger'}:kw['style']=style
    if icon:kw['icon_custom_emoji_id']=str(icon)
    try:return InlineKeyboardButton(label,**kw)
    except TypeError:
        kw.pop('style',None);kw.pop('icon_custom_emoji_id',None);return InlineKeyboardButton(label,**kw)
def keyboard(bs,code=None):
    rows=[]
    for b in bs or []:
        x=make_button(b,code)
        if not x:continue
        if len(b)>5 and b[5]=='same' and rows:rows[-1].append(x)
        else:rows.append([x])
    return InlineKeyboardMarkup(rows) if rows else None

def protect_for(chat_id):return False if is_admin(chat_id) else get_setting('protect_content')=='1'
async def send_cfg(chat_id,cfg,bot,code=None,reply_markup=None,force_protect=None):
    cfg=cfg or {};text=cfg.get('text') or '';es=deser_entities(cfg.get('entities',[]));mk=reply_markup or keyboard(cfg.get('buttons'),code);prot=protect_for(chat_id) if force_protect is None else force_protect;kw={'chat_id':chat_id,'protect_content':prot}
    if mk:kw['reply_markup']=mk
    mid,mt=cfg.get('media_id'),cfg.get('media_type')
    if mid:
        if text:kw['caption']=text;kw['caption_entities']=es
        if mt=='photo':return await bot.send_photo(photo=mid,**kw)
        if mt=='video':return await bot.send_video(video=mid,**kw)
        if mt=='animation':return await bot.send_animation(animation=mid,**kw)
        if mt=='document':return await bot.send_document(document=mid,**kw)
        if mt=='audio':return await bot.send_audio(audio=mid,**kw)
        if mt=='voice':return await bot.send_voice(voice=mid,**kw)
        if mt=='video_note':
            nk=dict(kw);nk.pop('reply_markup',None);nk.pop('caption',None);nk.pop('caption_entities',None);m=await bot.send_video_note(video_note=mid,**nk)
            if text:await bot.send_message(chat_id=chat_id,text=text,entities=es,reply_markup=mk,protect_content=prot)
            return m
    if text:return await bot.send_message(text=text,entities=es,**kw)
    if mk:return await bot.send_message(chat_id=chat_id,text='\u2063',reply_markup=mk,protect_content=prot)
async def send_file(chat_id,row,bot):
    es=deser_entities(row['caption_entities'] if 'caption_entities' in row.keys() else '[]');kw={'chat_id':chat_id,'protect_content':protect_for(chat_id)}
    if row['caption']:kw['caption']=row['caption'];kw['caption_entities']=es
    t,f=row['file_type'],row['file_id']
    if t=='photo':return await bot.send_photo(photo=f,**kw)
    if t=='video':return await bot.send_video(video=f,**kw)
    if t=='animation':return await bot.send_animation(animation=f,**kw)
    if t=='document':return await bot.send_document(document=f,**kw)
    if t=='audio':return await bot.send_audio(audio=f,**kw)
    if t=='voice':return await bot.send_voice(voice=f,**kw)
async def member(bot,cid,uid):
    try:return (await bot.get_chat_member(cid,uid)).status in {'member','administrator','creator','restricted'}
    except:return False
async def access(bot,uid):
    if is_admin(uid):return True
    if is_banned(uid):return False
    if await member(bot,MEMBERSHIP_GROUP_ID,uid):return True
    return await member(bot,CHANNEL_ID,uid) and await member(bot,FREE_GROUP_ID,uid)
async def deliver(update,context,x):
    sent=[];rows=get_batch(x) if x.startswith('B_') else ([get_file(x)] if get_file(x) else [])
    if not rows:await send_cfg(update.effective_chat.id,get_cfg('not_found_message'),context.bot);return
    for r in rows:
        if r:
            m=await send_file(update.effective_chat.id,r,context.bot)
            if m:sent.append(m.message_id)
    if sent and get_setting('auto_delete_enabled')=='1':
        mins=max(1,int(get_setting('auto_delete_minutes') or 10));cfg=get_cfg('auto_delete_notice');cfg['text']=(cfg.get('text') or DEFAULT_DELETE_NOTICE).replace('{minutes}',str(mins));n=await send_cfg(update.effective_chat.id,cfg,context.bot)
        if n:sent.append(n.message_id)
        async def d():
            await asyncio.sleep(mins*60)
            for mid in sent:
                try:await context.bot.delete_message(update.effective_chat.id,mid)
                except:pass
        asyncio.create_task(d())
async def start(update,context):
    save_user(update.effective_user);uid=update.effective_user.id
    if is_banned(uid):await send_cfg(update.effective_chat.id,get_cfg('banned_message'),context.bot);return
    if get_setting('maintenance')=='1' and not is_admin(uid):await send_cfg(update.effective_chat.id,get_cfg('maintenance_config'),context.bot);return
    if context.args:
        x=context.args[0]
        if not x.startswith(('F_','B_')):await send_cfg(update.effective_chat.id,get_cfg('invalid_link_message'),context.bot);return
        if not await access(context.bot,uid):await send_cfg(update.effective_chat.id,get_cfg('fsub_config'),context.bot,x,keyboard(get_cfg('fsub_config').get('buttons'),x));return
        await send_cfg(update.effective_chat.id,get_cfg('access_ok_message'),context.bot);await deliver(update,context,x);return
    await send_cfg(update.effective_chat.id,get_cfg('start_config'),context.bot)
async def check_cb(update,context):
    q=update.callback_query;uid=q.from_user.id
    if is_banned(uid):await q.answer('🚫 Kamu sedang dibanned.',show_alert=True);return
    if not await access(context.bot,uid):await q.answer('❌ Kamu belum memenuhi syarat akses.',show_alert=True);return
    await q.answer();cfg=get_cfg('access_ok_message')
    try:await q.edit_message_text(cfg.get('text') or DEFAULT_ACCESS_OK_TEXT,entities=deser_entities(cfg.get('entities',[])),reply_markup=keyboard(cfg.get('buttons')))
    except:pass
    await deliver(update,context,q.data.split(':',1)[1])

def home_kb():return InlineKeyboardMarkup([[InlineKeyboardButton('📊 Statistik',callback_data='adm:stats'),InlineKeyboardButton('📁 File',callback_data='adm:files')],[InlineKeyboardButton('🎨 Start',callback_data='adm:edit:start'),InlineKeyboardButton('📢 FSUB',callback_data='adm:edit:fsub')],[InlineKeyboardButton('👤 User Command',callback_data='adm:commands'),InlineKeyboardButton('📝 System Message',callback_data='adm:system')],[InlineKeyboardButton('👑 Admin',callback_data='adm:admins'),InlineKeyboardButton('🚫 Ban User',callback_data='adm:bans')],[InlineKeyboardButton('🗑️ Auto Delete',callback_data='adm:autodel'),InlineKeyboardButton('📢 Broadcast',callback_data='adm:broadcast')],[InlineKeyboardButton('💾 Backup',callback_data='adm:backup'),InlineKeyboardButton('🔧 Maintenance',callback_data='adm:maintenance')]])
def back(cb='adm:home'):return InlineKeyboardMarkup([[InlineKeyboardButton('⬅️ Kembali',callback_data=cb)]])
def cancel():return InlineKeyboardMarkup([[InlineKeyboardButton('❌ BATAL',callback_data='adm:cancel')]])
def editor(t):
    r=[[InlineKeyboardButton('📝 Text',callback_data=f'edit:text:{t}'),InlineKeyboardButton('🖼️ Media',callback_data=f'edit:media:{t}')]]
    if t.startswith('cmd/'):r.append([InlineKeyboardButton('🗒️ Deskripsi',callback_data=f'edit:desc:{t}')])
    r += [[InlineKeyboardButton('🔘 Buttons',callback_data=f'edit:buttons:{t}'),InlineKeyboardButton('👁️ Preview',callback_data=f'edit:preview:{t}')],[InlineKeyboardButton('💾 Simpan',callback_data=f'edit:save:{t}'),InlineKeyboardButton('🗑️ Hapus Media',callback_data=f'edit:delmedia:{t}')],[InlineKeyboardButton('⬅️ Kembali',callback_data='adm:back')]];return InlineKeyboardMarkup(r)
def target_cfg(t):
    if t.startswith('cmd/'):
        r=command_row(t[4:]);return json.loads(r['config']) if r else {}
    return get_cfg(t)
def save_target(t,c):
    if t=='start':set_cfg('start_config',c);set_setting('start_text',c.get('text',''));set_setting('start_entities',json.dumps(c.get('entities',[]),ensure_ascii=False));set_setting('start_media',c.get('media_id',''));set_setting('start_media_type',c.get('media_type',''))
    elif t.startswith('cmd/'):
        cdb=db();cdb.execute('UPDATE user_commands SET config=? WHERE command=?',(json.dumps(c,ensure_ascii=False),t[4:]));cdb.commit();cdb.close()
    else:set_cfg(t,c)
def begin(uid,t):admin_sessions[uid]={'target':t,'draft':json.loads(json.dumps(target_cfg(t),ensure_ascii=False)),'action':'editor'}
async def admin(update,context):
    uid=update.effective_user.id
    if not is_admin(uid):await send_cfg(update.effective_chat.id,get_cfg('denied_message'),context.bot);return
    admin_sessions[uid]={'action':'home'};await update.message.reply_text('👑 NAKAHOSHI ADMIN PANEL\n\nPilih menu:',reply_markup=home_kb(),protect_content=False)
async def admin_cb(update,context):
    q=update.callback_query;uid=q.from_user.id
    if not is_admin(uid):await q.answer('Tidak punya akses.',show_alert=True);return
    await q.answer();d=q.data
    if d=='adm:home':admin_sessions[uid]={'action':'home'};await q.edit_message_text('👑 NAKAHOSHI ADMIN PANEL\n\nPilih menu:',reply_markup=home_kb());return
    if d=='adm:back':
        s=admin_sessions.get(uid,{})
        if s.get('target'):await q.edit_message_text(f"⚙️ EDIT {s['target'].upper()}\n\nSemua perubahan masih draft sampai disimpan.",reply_markup=editor(s['target']))
        else:await q.edit_message_text('👑 NAKAHOSHI ADMIN PANEL\n\nPilih menu:',reply_markup=home_kb())
        return
    if d=='adm:cancel':
        s=admin_sessions.get(uid,{})
        if s.get('target'):begin(uid,s['target']);await q.edit_message_text(f"⚙️ EDIT {s['target'].upper()}\n\n❌ Input dibatalkan. Draft dikembalikan ke data tersimpan.",reply_markup=editor(s['target']))
        else:admin_sessions.pop(uid,None);await q.edit_message_text('👑 NAKAHOSHI ADMIN PANEL\n\nPilih menu:',reply_markup=home_kb())
        return
    if d in ('adm:edit:start','adm:edit:fsub'):
        t=d.split(':')[-1];begin(uid,t);await q.edit_message_text(f'⚙️ EDIT {t.upper()}\n\nText + Media + Buttons + Preview.\nSemua perubahan masih draft sampai disimpan.',reply_markup=editor(t));return
    if d=='adm:stats':
        c=db();v=[c.execute('SELECT COUNT(*) FROM files').fetchone()[0],c.execute('SELECT COUNT(*) FROM batches').fetchone()[0],c.execute('SELECT COUNT(*) FROM users').fetchone()[0],c.execute('SELECT COUNT(*) FROM banned_users').fetchone()[0]];c.close();await q.edit_message_text(f'📊 STATISTIK\n\n📁 File: {v[0]}\n📦 Batch: {v[1]}\n👥 User: {v[2]}\n🚫 Banned: {v[3]}',reply_markup=back());return
    if d=='adm:files':
        c=db();r=c.execute('SELECT code,file_type FROM files ORDER BY rowid DESC LIMIT 20').fetchall();c.close();await q.edit_message_text('📁 FILE TERBARU\n\n'+('\n'.join(f"{x['code']} — {x['file_type']}" for x in r) if r else 'Belum ada file.'),reply_markup=back());return
    if d=='adm:commands':
        c=db();r=c.execute('SELECT command,description,enabled FROM user_commands ORDER BY command').fetchall();c.close();kb=[[InlineKeyboardButton(('🟢 ' if x['enabled'] else '🔴 ')+f"/{x['command']}",callback_data=f"adm:cmd:{x['command']}")] for x in r];kb += [[InlineKeyboardButton('➕ Tambah Command',callback_data='adm:addcmd')],[InlineKeyboardButton('⬅️ Kembali',callback_data='adm:home')]];await q.edit_message_text('👤 USER COMMAND\n\nPilih command:',reply_markup=InlineKeyboardMarkup(kb));return
    if d.startswith('adm:cmd:'):
        t='cmd/'+d.split(':',2)[2];begin(uid,t);r=command_row(t[4:]);kb=editor(t).inline_keyboard;kb.append([InlineKeyboardButton('🔄 Aktif/Nonaktif',callback_data=f'adm:toggle:{t[4:]}'),InlineKeyboardButton('🗑️ Hapus',callback_data=f'adm:deletecmd:{t[4:]}')]);await q.edit_message_text(f"⚙️ EDIT /{t[4:]}\nStatus: {'🟢 AKTIF' if r and r['enabled'] else '🔴 NONAKTIF'}\nDeskripsi: {(r['description'] if r else '')[:256]}",reply_markup=InlineKeyboardMarkup(kb));return
    if d=='adm:addcmd':admin_sessions[uid]={'action':'add_command'};await q.edit_message_text('➕ TAMBAH COMMAND\n\nKirim: /nama | Deskripsi',reply_markup=cancel());return
    if d.startswith('adm:toggle:'):
        x=d.split(':',2)[2];c=db();r=c.execute('SELECT enabled FROM user_commands WHERE command=?',(x,)).fetchone()
        if r:c.execute('UPDATE user_commands SET enabled=? WHERE command=?',(0 if r['enabled'] else 1,x));c.commit()
        c.close();await refresh_commands(context.bot);await q.edit_message_text(f'🔄 /{x} diubah.',reply_markup=back());return
    if d.startswith('adm:deletecmd:'):
        x=d.split(':',2)[2];c=db();c.execute('DELETE FROM user_commands WHERE command=?',(x,));c.commit();c.close();admin_sessions.pop(uid,None);await refresh_commands(context.bot);await q.edit_message_text(f'🗑️ /{x} dihapus.',reply_markup=back());return
    if d=='adm:system':
        keys=[('banned_message','🚫 Pesan Banned'),('denied_message','⛔ Command Ditolak'),('not_found_message','❌ File Tidak Ditemukan'),('invalid_link_message','🔗 Link Tidak Valid'),('access_ok_message','✅ Akses OK'),('cs_config','🛠️ Customer Service'),('unban_config','♻️ Unban'),('auto_delete_notice','🗑️ Auto Delete'),('maintenance_config','🔧 Maintenance')];kb=[[InlineKeyboardButton(b,callback_data=f'adm:sys:{a}')] for a,b in keys];kb.append([InlineKeyboardButton('⬅️ Kembali',callback_data='adm:home')]);await q.edit_message_text('📝 SYSTEM MESSAGE\n\nPilih pesan:',reply_markup=InlineKeyboardMarkup(kb));return
    if d.startswith('adm:sys:'):
        t=d.split(':',2)[2];begin(uid,t);await q.edit_message_text(f'📝 EDIT {t.upper()}\n\nBisa Text + Media + Buttons + Preview.',reply_markup=editor(t));return
    if d=='adm:admins':
        c=db();r=c.execute('SELECT user_id FROM admins ORDER BY user_id').fetchall();c.close();txt='👑 ADMIN\n\n'+'\n'.join(f"{x['user_id']}"+(' — OWNER' if x['user_id']==OWNER_ID else '') for x in r);await q.edit_message_text(txt,reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('➕ Tambah Admin',callback_data='adm:addadmin')],[InlineKeyboardButton('🗑️ Hapus Admin',callback_data='adm:deladmin')],[InlineKeyboardButton('⬅️ Kembali',callback_data='adm:home')]]));return
    if d in ('adm:addadmin','adm:deladmin'):admin_sessions[uid]={'action':'add_admin' if d.endswith('addadmin') else 'del_admin'};await q.edit_message_text('➕ TAMBAH ADMIN\n\nKirim Telegram User ID.' if d.endswith('addadmin') else '🗑️ HAPUS ADMIN\n\nKirim Telegram User ID. Owner tidak dapat dihapus.',reply_markup=cancel());return
    if d=='adm:bans':
        c=db();r=c.execute('SELECT user_id,reason FROM banned_users ORDER BY banned_at DESC LIMIT 50').fetchall();c.close();txt='🚫 BANNED USERS\n\n'+('\n'.join(f"{x['user_id']} — {x['reason'] or '-'}" for x in r) if r else 'Belum ada user banned.');await q.edit_message_text(txt,reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔨 Ban User',callback_data='adm:ban')],[InlineKeyboardButton('♻️ Unban User',callback_data='adm:unban')],[InlineKeyboardButton('⬅️ Kembali',callback_data='adm:home')]]));return
    if d in ('adm:ban','adm:unban'):admin_sessions[uid]={'action':d.split(':')[1]};await q.edit_message_text('🔨 BAN USER\n\nKirim User ID.\nOpsional alasan: 123 | alasan' if d.endswith('ban') else '♻️ UNBAN USER\n\nKirim User ID.',reply_markup=cancel());return
    if d=='adm:autodel':
        st='🟢 AKTIF' if get_setting('auto_delete_enabled')=='1' else '🔴 NONAKTIF';await q.edit_message_text(f"🗑️ AUTO DELETE FILE\n\nStatus: {st}\nWaktu: {get_setting('auto_delete_minutes')} menit",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🟢 Aktifkan',callback_data='adm:ad:on'),InlineKeyboardButton('🔴 Matikan',callback_data='adm:ad:off')],[InlineKeyboardButton('⏱️ Atur Waktu',callback_data='adm:ad:time'),InlineKeyboardButton('📝 Notifikasi',callback_data='adm:ad:msg')],[InlineKeyboardButton('⬅️ Kembali',callback_data='adm:home')]]));return
    if d=='adm:ad:on':set_setting('auto_delete_enabled','1');await q.edit_message_text('🟢 Auto Delete aktif.',reply_markup=back());return
    if d=='adm:ad:off':set_setting('auto_delete_enabled','0');await q.edit_message_text('🔴 Auto Delete dimatikan.',reply_markup=back());return
    if d=='adm:ad:time':admin_sessions[uid]={'action':'ad_time'};await q.edit_message_text('⏱️ Kirim jumlah menit.',reply_markup=cancel());return
    if d=='adm:ad:msg':begin(uid,'auto_delete_notice');await q.edit_message_text('📝 EDIT NOTIFIKASI AUTO DELETE',reply_markup=editor('auto_delete_notice'));return
    if d=='adm:broadcast':admin_sessions[uid]={'action':'broadcast'};await q.edit_message_text('📢 BROADCAST\n\nKirim satu pesan/media.\nSetelah itu /broadcast_confirm untuk kirim.',reply_markup=cancel());return
    if d=='adm:backup':
        try:
            with open(DB_NAME,'rb') as f:await context.bot.send_document(uid,f,caption='💾 Backup database NakaFileBOT',protect_content=False)
        except Exception as e:await q.answer('Backup gagal: '+str(e)[:100],show_alert=True)
        return
    if d=='adm:maintenance':
        st='🟢 AKTIF' if get_setting('maintenance')=='1' else '🔴 NONAKTIF';await q.edit_message_text(f'🔧 MAINTENANCE\n\nStatus: {st}',reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🟢 Aktifkan',callback_data='adm:maint:on'),InlineKeyboardButton('🔴 Matikan',callback_data='adm:maint:off')],[InlineKeyboardButton('📝 Edit Pesan',callback_data='adm:maint:msg')],[InlineKeyboardButton('⬅️ Kembali',callback_data='adm:home')]]));return
    if d=='adm:maint:on':set_setting('maintenance','1');await q.edit_message_text('🟢 Maintenance aktif.',reply_markup=back());return
    if d=='adm:maint:off':set_setting('maintenance','0');await q.edit_message_text('🔴 Maintenance dimatikan.',reply_markup=back());return
    if d=='adm:maint:msg':begin(uid,'maintenance_config');await q.edit_message_text('📝 EDIT PESAN MAINTENANCE',reply_markup=editor('maintenance_config'));return
    if d.startswith('edit:'):
        _,a,t=d.split(':',2);s=admin_sessions.get(uid)
        if not s or s.get('target')!=t:begin(uid,t);s=admin_sessions[uid]
        c=s['draft']
        if a=='text':s['action']='edit_text';await q.edit_message_text('📝 KIRIM TEKS BARU\n\nFormatting Telegram + Premium Custom Emoji akan ikut tersimpan.',reply_markup=cancel());return
        if a=='desc':s['action']='edit_desc';await q.edit_message_text('🗒️ KIRIM DESKRIPSI COMMAND BARU\n\nBacaan/description command di menu Telegram. Maksimal 256 karakter.',reply_markup=cancel());return
        if a=='media':s['action']='edit_media';await q.edit_message_text('🖼️ KIRIM MEDIA\n\nFoto, GIF, Video, Dokumen, Audio, Voice, atau Video Note.\n\nMedia baru hanya masuk DRAFT sampai SIMPAN.',reply_markup=cancel());return
        if a=='delmedia':c['media_id']='';c['media_type']='';await q.edit_message_text('🗑️ Media dihapus dari draft. Belum tersimpan.',reply_markup=editor(t));return
        if a=='buttons':await buttons_menu(q,uid,t);return
        if a=='preview':await preview(q,context,uid,t,c);return
        if a=='previewback':await q.edit_message_text(f'⚙️ EDIT {t.upper()}\n\nSemua perubahan masih draft sampai disimpan.',reply_markup=editor(t));return
        if a=='save':save_target(t,c);admin_sessions.pop(uid,None);await q.edit_message_text('💾 PERUBAHAN TERSIMPAN.',reply_markup=back());return
async def buttons_menu(q,uid,t):
    bs=admin_sessions[uid]['draft'].get('buttons',[]);kb=[[InlineKeyboardButton(f'✏️ {b[0]}',callback_data=f'btn:edit:{t}:{i}'),InlineKeyboardButton('🗑️',callback_data=f'btn:del:{t}:{i}')] for i,b in enumerate(bs)];kb += [[InlineKeyboardButton('➕ Tambah Button',callback_data=f'btn:add:{t}')],[InlineKeyboardButton('⬅️ Editor',callback_data=f'btn:back:{t}')]];await q.edit_message_text('🔘 BUTTON MANAGER\n\nSemua perubahan masih di draft.\n\nStyle: #g hijau, #r merah, #p biru.\n&& untuk baris yang sama.\nCustom emoji ID bisa ditulis sebagai kolom terakhir.',reply_markup=InlineKeyboardMarkup(kb))
async def preview(q,context,uid,t,c):
    await q.edit_message_text('👁️ PREVIEW\n\nIni preview dari DRAFT. Belum disimpan.',reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('⬅️ Editor',callback_data=f'edit:previewback:{t}')]]));await send_cfg(q.message.chat_id,c,context.bot,force_protect=False)
async def button_cb(update,context):
    q=update.callback_query;uid=q.from_user.id
    if not is_admin(uid):await q.answer('Tidak punya akses.',show_alert=True);return
    await q.answer();p=q.data.split(':');a,t=p[1],p[2];s=admin_sessions.get(uid)
    if not s or s.get('target')!=t:return
    if a=='back':await q.edit_message_text(f'⚙️ EDIT {t.upper()}',reply_markup=editor(t));return
    if a=='add':s['action']='add_button';await q.edit_message_text('➕ TAMBAH BUTTON\n\nFormat:\nNama | URL | #g/#r/#p | custom_emoji_id\n\nKirim beberapa baris untuk beberapa button. Gunakan && pada baris yang sama.',reply_markup=cancel());return
    i=int(p[3]);bs=s['draft'].setdefault('buttons',[])
    if a=='del':bs.pop(i);await buttons_menu(q,uid,t);return
    if a=='edit':s['action']='edit_button';s['button_index']=i;await q.edit_message_text(f"✏️ EDIT BUTTON\n\nSaat ini: {bs[i][0]}\nURL: {bs[i][2] if len(bs[i])>2 else ''}\nStyle: {bs[i][3] if len(bs[i])>3 else '-'}\nIcon: {bs[i][4] if len(bs[i])>4 else '-'}\n\nKirim format baru.",reply_markup=cancel());return
async def media_in(update,context):
    uid=update.effective_user.id
    if not is_admin(uid):return
    s=admin_sessions.get(uid);m=update.message;a=s.get('action') if s else None
    if a=='broadcast':s['broadcast_message_id']=m.message_id;s['action']='broadcast_confirm';await m.reply_text('📢 Pesan siap dibroadcast. /broadcast_confirm untuk kirim atau /cancel untuk batal.',protect_content=False);return
    if a=='edit_media':
        c=s['draft']
        if m.photo:c['media_id']=m.photo[-1].file_id;c['media_type']='photo'
        elif m.video:c['media_id']=m.video.file_id;c['media_type']='video'
        elif m.animation:c['media_id']=m.animation.file_id;c['media_type']='animation'
        elif m.document:c['media_id']=m.document.file_id;c['media_type']='document'
        elif m.audio:c['media_id']=m.audio.file_id;c['media_type']='audio'
        elif m.voice:c['media_id']=m.voice.file_id;c['media_type']='voice'
        elif m.video_note:c['media_id']=m.video_note.file_id;c['media_type']='video_note'
        else:return
        if m.caption is not None:c['text']=m.caption;c['entities']=ser_entities(m.caption_entities)
        s['action']='editor';await m.reply_text('🖼️ Media masuk DRAFT. Belum disimpan.',reply_markup=editor(uid,s['target']),protect_content=False);return
    if a in (None,'editor') and (m.photo or m.video or m.animation or m.document or m.audio or m.voice):
        if m.photo:f,t=m.photo[-1].file_id,'photo'
        elif m.video:f,t=m.video.file_id,'video'
        elif m.animation:f,t=m.animation.file_id,'animation'
        elif m.document:f,t=m.document.file_id,'document'
        elif m.audio:f,t=m.audio.file_id,'audio'
        else:f,t=m.voice.file_id,'voice'
        item=(f,t,m.caption or '',m.caption_entities or []);p=pending_batches.get(uid)
        if p is not None:p.append(item);await m.reply_text(f'✅ Ditambahkan ke batch. Total: {len(p)}',protect_content=False);return
        x=create_file(*item);await m.reply_text(f'✅ File tersimpan!\n\n🔗 https://t.me/{context.bot.username}?start={x}\n\nCode: {x}',protect_content=False)
async def text_in(update,context):
    uid=update.effective_user.id
    if not is_admin(uid):return
    m=update.message;s=admin_sessions.get(uid);a=s.get('action') if s else None
    if a=='broadcast':s['broadcast_message_id']=m.message_id;s['action']='broadcast_confirm';await m.reply_text('📢 Pesan siap dibroadcast. /broadcast_confirm untuk kirim atau /cancel untuk batal.',protect_content=False);return
    if a=='add_command':
        z=re.match(r'^/?([A-Za-z0-9_]+)\s*\|\s*(.+)$',m.text or '')
        if not z:await m.reply_text('Format salah: /help | Bantuan Nakahoshi',protect_content=False);return
        cmd,desc=z.group(1).lower(),z.group(2);reserved={'start','admin','batch','done','cancelbatch','cancel','broadcast','broadcast_confirm','setpayment','setchannel','setgroup','setowner'}
        if cmd in reserved:await m.reply_text('❌ Nama command dipakai sistem.',protect_content=False);return
        c=db();ex=c.execute('SELECT 1 FROM user_commands WHERE command=?',(cmd,)).fetchone()
        if ex:c.close();await m.reply_text('❌ Command sudah ada.',protect_content=False);return
        c.execute('INSERT INTO user_commands(command,description,config,enabled) VALUES(?,?,?,1)',(cmd,desc,json.dumps({'text':'Tulis isi command ini...','entities':[],'media_id':'','media_type':'','buttons':[]},ensure_ascii=False)));c.commit();c.close();admin_sessions.pop(uid,None);await refresh_commands(context.bot);await m.reply_text(f'✅ /{cmd} dibuat.',protect_content=False);return
    if a in ('add_admin','del_admin'):
        try:x=int((m.text or '').strip())
        except:await m.reply_text('❌ User ID harus angka.',protect_content=False);return
        if a=='del_admin' and x==OWNER_ID:await m.reply_text('🚫 Owner utama tidak dapat dihapus.',protect_content=False);return
        c=db();c.execute('DELETE FROM admins WHERE user_id=?',(x,)) if a=='del_admin' else c.execute('INSERT OR IGNORE INTO admins(user_id,added_at,added_by) VALUES(?,?,?)',(x,datetime.now().isoformat(timespec='seconds'),uid));c.commit();c.close();admin_sessions.pop(uid,None);await m.reply_text('✅ Selesai.',protect_content=False);return
    if a in ('ban','unban'):
        z=(m.text or '').split('|',1)
        try:x=int(z[0].strip())
        except:await m.reply_text('❌ User ID harus angka.',protect_content=False);return
        c=db()
        if a=='ban':
            if x in admins():c.close();await m.reply_text('🚫 Admin tidak dapat dibanned.',protect_content=False);return
            c.execute('INSERT OR REPLACE INTO banned_users(user_id,reason,banned_at,banned_by) VALUES(?,?,?,?)',(x,z[1].strip() if len(z)>1 else '',datetime.now().isoformat(timespec='seconds'),uid))
        else:c.execute('DELETE FROM banned_users WHERE user_id=?',(x,))
        c.commit();c.close();admin_sessions.pop(uid,None);await m.reply_text('✅ Selesai.',protect_content=False);return
    if a=='ad_time':
        try:x=max(1,int((m.text or '').strip()))
        except:await m.reply_text('❌ Masukkan angka menit minimal 1.',protect_content=False);return
        set_setting('auto_delete_minutes',str(x));admin_sessions.pop(uid,None);await m.reply_text(f'⏱️ {x} menit.',protect_content=False);return
    if a=='edit_text':s['draft']['text']=m.text or '';s['draft']['entities']=ser_entities(m.entities);s['action']='editor';await m.reply_text('📝 Text masuk DRAFT. Premium Custom Emoji + formatting ikut tersimpan.',reply_markup=editor(uid,s['target']),protect_content=False);return
    if a=='edit_desc':
        t=s.get('target','');cmd=t[4:] if t.startswith('cmd/') else '';c=db();c.execute('UPDATE user_commands SET description=? WHERE command=?',((m.text or '')[:256],cmd));c.commit();c.close();s['action']='editor';await refresh_commands(context.bot);await m.reply_text('🗒️ Deskripsi berhasil diubah.',reply_markup=editor(uid,t),protect_content=False);return
    if a in ('add_button','edit_button'):
        lines=[]
        for line in (m.text or '').splitlines():lines += [x.strip() for x in line.split('&&') if x.strip()]
        if a=='edit_button':lines=lines[:1]
        for n,line in enumerate(lines):
            p=[x.strip() for x in line.split('|')]
            if len(p)<2 or not re.match(r'^https?://\S+$',p[1]):await m.reply_text('Format salah: Nama | URL | #g/#r/#p | custom_emoji_id',protect_content=False);return
            label,url=p[0],p[1];style=None;icon=None
            for x in p[2:]:
                if x.lower()=='#g':style='success'
                elif x.lower()=='#r':style='danger'
                elif x.lower()=='#p':style='primary'
                elif x:icon=x
            for e in m.entities or []:
                if e.type=='custom_emoji' and getattr(e,'custom_emoji_id',None):icon=e.custom_emoji_id;break
            b=[label,'url',url,style,icon,'same' if n else 'new']
            if a=='add_button':s['draft'].setdefault('buttons',[]).append(b)
            else:s['draft']['buttons'][s.get('button_index',0)]=b
        s['action']='editor';await m.reply_text('🔘 Button masuk DRAFT. Belum disimpan.',reply_markup=editor(uid,s['target']),protect_content=False)
async def cancel_cmd(update,context):
    uid=update.effective_user.id
    if is_admin(uid):
        s=admin_sessions.get(uid,{})
        if s.get('target'):begin(uid,s['target']);await update.message.reply_text('❌ Input dibatalkan. Kembali ke editor.',reply_markup=editor(uid,s['target']),protect_content=False)
        else:admin_sessions.pop(uid,None);pending_batches.pop(uid,None);await update.message.reply_text('❌ Dibatalkan.',protect_content=False)
async def batch_cmd(update,context):
    if is_admin(update.effective_user.id):pending_batches[update.effective_user.id]=[];await update.message.reply_text('📦 MODE BATCH AKTIF\n\nKirim file lalu /done.\nBatal /cancelbatch',protect_content=False)
async def done_cmd(update,context):
    uid=update.effective_user.id
    if not is_admin(uid):return
    p=pending_batches.pop(uid,None)
    if p is None or not p:await update.message.reply_text('❌ Batch kosong.',protect_content=False);return
    x=create_batch(uid,p);await update.message.reply_text(f'✅ BATCH SELESAI\n\n📦 Total: {len(p)}\n🔗 https://t.me/{context.bot.username}?start={x}\n\nCode: {x}',protect_content=False)
async def broadcast_cmd(update,context):
    if is_admin(update.effective_user.id):admin_sessions[update.effective_user.id]={'action':'broadcast'};await update.message.reply_text('📢 BROADCAST\n\nKirim pesan/media lalu /broadcast_confirm.',protect_content=False)
async def broadcast_confirm(update,context):
    uid=update.effective_user.id;s=admin_sessions.get(uid)
    if not is_admin(uid) or not s or s.get('action')!='broadcast_confirm':return
    c=db();users=[x['user_id'] for x in c.execute('SELECT user_id FROM users')];c.close();ok=bad=0
    for x in users:
        try:await context.bot.copy_message(chat_id=x,from_chat_id=uid,message_id=s['broadcast_message_id'],protect_content=True);ok+=1
        except:bad+=1
        await asyncio.sleep(.04)
    admin_sessions.pop(uid,None);await update.message.reply_text(f'📢 BROADCAST SELESAI\n\n✅ {ok}\n❌ {bad}',protect_content=False)
async def generic(update,context):
    cmd=update.message.text.split()[0].lstrip('/').split('@')[0].lower()
    if cmd in {'start','admin','batch','done','cancelbatch','cancel','broadcast','broadcast_confirm','setpayment','setchannel','setgroup','setowner'}:return
    save_user(update.effective_user)
    if is_banned(update.effective_user.id):await send_cfg(update.effective_chat.id,get_cfg('banned_message'),context.bot);return
    r=command_row(cmd)
    if r and r['enabled']:await send_cfg(update.effective_chat.id,json.loads(r['config']),context.bot)
async def setlink(update,context,k,label):
    if is_admin(update.effective_user.id) and context.args:set_setting(k,' '.join(context.args));await update.message.reply_text(f'✅ {label} berhasil diubah.',protect_content=False)
async def setpayment(update,context):await setlink(update,context,'payment_link','Payment link')
async def setchannel(update,context):await setlink(update,context,'channel_link','Channel link')
async def setgroup(update,context):await setlink(update,context,'free_group_link','Group link')
async def setowner(update,context):await setlink(update,context,'owner_link','Owner link')
async def refresh_commands(bot):
    c=db();r=c.execute('SELECT command,description FROM user_commands WHERE enabled=1 ORDER BY rowid').fetchall();c.close();base=[BotCommand('start','Buka bot / akses file')]+[BotCommand(x['command'],(x['description'] or '')[:256]) for x in r];await bot.set_my_commands(base,scope=BotCommandScopeDefault())
    for uid in admins():
        try:await bot.set_my_commands(base+[BotCommand('admin','Admin panel'),BotCommand('batch','Mulai batch'),BotCommand('done','Selesai batch'),BotCommand('cancelbatch','Batal batch'),BotCommand('cancel','Batal proses'),BotCommand('broadcast','Broadcast'),BotCommand('broadcast_confirm','Konfirmasi broadcast')],scope=BotCommandScopeChat(chat_id=uid))
        except Exception as e:print('command menu error',uid,e)
async def post_init(app):await refresh_commands(app.bot)
async def errors(update,context):print('ERROR:',context.error)
def main():
    init_db();app=Application.builder().token(TOKEN).post_init(post_init).build();app.add_handler(CommandHandler('start',start));app.add_handler(CommandHandler('admin',admin));app.add_handler(CommandHandler('batch',batch_cmd));app.add_handler(CommandHandler('done',done_cmd));app.add_handler(CommandHandler('cancelbatch',cancel_cmd));app.add_handler(CommandHandler('cancel',cancel_cmd));app.add_handler(CommandHandler('broadcast',broadcast_cmd));app.add_handler(CommandHandler('broadcast_confirm',broadcast_confirm));app.add_handler(CommandHandler('setpayment',setpayment));app.add_handler(CommandHandler('setchannel',setchannel));app.add_handler(CommandHandler('setgroup',setgroup));app.add_handler(CommandHandler('setowner',setowner));app.add_handler(CallbackQueryHandler(check_cb,pattern=r'^check:'));app.add_handler(CallbackQueryHandler(admin_cb,pattern=r'^(adm:|edit:)'));app.add_handler(CallbackQueryHandler(button_cb,pattern=r'^btn:'));mf=filters.PHOTO|filters.VIDEO|filters.ANIMATION|filters.Document.ALL|filters.AUDIO|filters.VOICE|filters.VIDEO_NOTE;app.add_handler(MessageHandler(mf,media_in));app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,text_in));app.add_handler(MessageHandler(filters.COMMAND,generic));app.add_error_handler(errors);app.run_polling(allowed_updates=Update.ALL_TYPES)
if __name__=='__main__':main()
