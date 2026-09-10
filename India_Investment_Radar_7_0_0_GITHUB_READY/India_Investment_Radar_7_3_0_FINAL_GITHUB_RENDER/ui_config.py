from __future__ import annotations
from pathlib import Path
import base64, json, mimetypes

BASE=Path(__file__).resolve().parent
DATA=BASE/'data'
DATA.mkdir(parents=True,exist_ok=True)
SETTINGS_FILE=DATA/'ui_settings.json'
BG_DIR=DATA/'ui_assets'
BG_DIR.mkdir(parents=True,exist_ok=True)

PRESETS={
    'Professional Navy':{
        'primary':'#0A1426','primary2':'#172B4D','accent':'#C7A552','accent2':'#E4CB82',
        'app_bg':'#F4F7FB','card':'#FFFFFF','ink':'#172033','muted':'#667085','line':'#E5EAF1','sidebar':'#0A1426',
        'success':'#177245','warning':'#A15C00','danger':'#B42318'
    },
    'Clean Light':{
        'primary':'#16243A','primary2':'#2C3E57','accent':'#9B7B2F','accent2':'#C3A55C',
        'app_bg':'#F8FAFC','card':'#FFFFFF','ink':'#162033','muted':'#667085','line':'#E6EAF0','sidebar':'#FFFFFF',
        'success':'#166534','warning':'#A16207','danger':'#B91C1C'
    },
    'Dark Terminal':{
        'primary':'#07111E','primary2':'#102437','accent':'#D8B45B','accent2':'#F0D27D',
        'app_bg':'#07111E','card':'#0D1A29','ink':'#EAF0F7','muted':'#A7B2C2','line':'#213247','sidebar':'#050B13',
        'success':'#35B879','warning':'#E9A23B','danger':'#F97066'
    },
    'Minimal White':{
        'primary':'#111827','primary2':'#243244','accent':'#B78B2F','accent2':'#D3AF5D',
        'app_bg':'#FFFFFF','card':'#FFFFFF','ink':'#111827','muted':'#6B7280','line':'#E5E7EB','sidebar':'#111827',
        'success':'#15803D','warning':'#B45309','danger':'#B91C1C'
    },
}
PRESETS['Custom']=dict(PRESETS['Professional Navy'])

DEFAULT_SETTINGS={
    'theme_preset':'Professional Navy',
    'background_mode':'Abstract Market',
    'background_path':'',
    'background_opacity':0.12,
    'background_blur':0,
    'background_overlay':0.0,
    'card_opacity':0.97,
    'font_scale':1.0,
    'density':'Comfortable',
    'radius':14,
    'default_page':'📣 Daily Recommendations',
    'show_background_on_analysis_pages':False,
    'custom_colors':{},
}


def load_ui_settings():
    out=dict(DEFAULT_SETTINGS)
    if SETTINGS_FILE.exists():
        try:
            raw=json.loads(SETTINGS_FILE.read_text(encoding='utf-8'))
            if isinstance(raw,dict):out.update(raw)
        except Exception:pass
    if out.get('theme_preset') not in PRESETS:out['theme_preset']='Professional Navy'
    return out


def save_ui_settings(settings:dict):
    data=dict(DEFAULT_SETTINGS);data.update(settings or {})
    SETTINGS_FILE.write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8')
    return data


def reset_ui_settings():
    save_ui_settings(DEFAULT_SETTINGS)
    return dict(DEFAULT_SETTINGS)


def save_background(uploaded):
    if uploaded is None:return ''
    name=str(getattr(uploaded,'name','background.png'))
    ext=Path(name).suffix.lower()
    if ext not in ('.png','.jpg','.jpeg','.webp'):ext='.png'
    for old in BG_DIR.glob('background.*'):
        try:old.unlink()
        except Exception:pass
    path=BG_DIR/f'background{ext}'
    data=uploaded.getvalue() if hasattr(uploaded,'getvalue') else uploaded.read()
    path.write_bytes(data)
    return str(path.relative_to(BASE)).replace('\\','/')


def clear_background():
    for old in BG_DIR.glob('background.*'):
        try:old.unlink()
        except Exception:pass


def _color(settings,key,preset):
    cc=settings.get('custom_colors') or {}
    return str(cc.get(key) or PRESETS[preset].get(key) or '#000000')


def _bg_data_uri(rel):
    if not rel:return ''
    p=(BASE/rel).resolve()
    try:
        if not p.exists() or BASE.resolve() not in p.parents:return ''
        mime=mimetypes.guess_type(str(p))[0] or 'image/png'
        return f'data:{mime};base64,'+base64.b64encode(p.read_bytes()).decode('ascii')
    except Exception:return ''


def _hex_rgb(h):
    h=str(h).strip().lstrip('#')
    if len(h)==3:h=''.join(c*2 for c in h)
    try:return tuple(int(h[i:i+2],16) for i in (0,2,4))
    except Exception:return (0,0,0)

def _mix(a,b,weight_a=0.5):
    ra,ga,ba=_hex_rgb(a);rb,gb,bb=_hex_rgb(b);w=max(0,min(1,float(weight_a)))
    vals=[round(x*w+y*(1-w)) for x,y in ((ra,rb),(ga,gb),(ba,bb))]
    return '#'+''.join(f'{v:02X}' for v in vals)

def _rgba(h,alpha):
    r,g,b=_hex_rgb(h);return f'rgba({r},{g},{b},{max(0,min(1,float(alpha))):.3f})'

def build_css(settings:dict, analysis_page:bool=False):
    s=dict(DEFAULT_SETTINGS);s.update(settings or {})
    preset=s.get('theme_preset','Professional Navy')
    if preset not in PRESETS:preset='Professional Navy'
    dark=(preset=='Dark Terminal')
    primary=_color(s,'primary',preset);primary2=_color(s,'primary2',preset);accent=_color(s,'accent',preset);accent2=_color(s,'accent2',preset)
    app_bg=_color(s,'app_bg',preset);card=_color(s,'card',preset);ink=_color(s,'ink',preset);muted=_color(s,'muted',preset);line=_color(s,'line',preset);sidebar=_color(s,'sidebar',preset)
    success=_color(s,'success',preset);warning=_color(s,'warning',preset);danger=_color(s,'danger',preset)
    fs=max(.85,min(1.25,float(s.get('font_scale',1.0) or 1.0)))
    radius=max(6,min(28,int(s.get('radius',14) or 14)))
    density=s.get('density','Comfortable');pad='0.72rem' if density=='Compact' else ('1.22rem' if density=='Spacious' else '1rem')
    mode=s.get('background_mode','Abstract Market')
    show_bg=(not analysis_page) or bool(s.get('show_background_on_analysis_pages'))
    bg='none'
    if show_bg:
        if mode=='Gradient':
            bg=f'linear-gradient(145deg,{app_bg} 0%, {_mix(accent,app_bg,.10)} 50%, {app_bg} 100%)'
        elif mode=='Abstract Market':
            # CSS-only professional market-grid atmosphere; intentionally low contrast.
            bg=(f'linear-gradient(rgba(255,255,255,{0.84 if not dark else 0.02}),rgba(255,255,255,{0.84 if not dark else 0.02})),'
                f'repeating-linear-gradient(0deg,transparent 0 31px,{_rgba(accent,.07)} 32px),' 
                f'repeating-linear-gradient(90deg,transparent 0 47px,{_rgba(primary2,.05)} 48px),' 
                f'radial-gradient(circle at 85% 8%,{_rgba(accent,.12)},transparent 28%),'
                f'linear-gradient(180deg,{app_bg},{_mix(primary,app_bg,.04)})')
        elif mode=='Custom Image':
            uri=_bg_data_uri(s.get('background_path',''))
            if uri:
                overlay=max(0,min(.9,float(s.get('background_overlay',0.0) or 0.0)))
                # darker overlay for readability while preserving image.
                bg=f'linear-gradient(rgba(8,15,28,{overlay}),rgba(8,15,28,{overlay})),url("{uri}") center/cover fixed no-repeat'
        elif mode=='Solid':
            bg=app_bg
    if bg=='none':bg=app_bg
    side_text='#F8FAFC' if preset!='Clean Light' else '#172033'
    side_muted='#AAB5C7' if preset!='Clean Light' else '#667085'
    hero1=primary;hero2=primary2
    return f'''<style id="radar-dynamic-theme">
:root{{--radar-navy:{primary};--radar-navy-2:{primary2};--radar-gold:{accent};--radar-gold-soft:{_mix(accent,'#FFFFFF',.16)};--radar-ink:{ink};--radar-muted:{muted};--radar-line:{line};--radar-bg:{app_bg};--radar-card:{card};--radar-success:{success};--radar-warning:{warning};--radar-danger:{danger};}}
html{{font-size:{fs*100:.1f}%}}
.stApp{{background:{bg}!important;color:{ink}!important;}}
.block-container{{padding-left:{pad};padding-right:{pad};}}
[data-testid="stSidebar"]{{background:{sidebar}!important;border-right:1px solid {line}!important;}}
[data-testid="stSidebar"] h1,[data-testid="stSidebar"] h2,[data-testid="stSidebar"] h3,[data-testid="stSidebar"] label,[data-testid="stSidebar"] p{{color:{side_text}!important;}}
[data-testid="stSidebar"] .stCaptionContainer p{{color:{side_muted}!important;}}
[data-testid="stSidebar"] div[data-baseweb="select"]>div{{background:{_mix(sidebar,'#FFFFFF',.92)}!important;border-color:{_mix(sidebar,'#FFFFFF',.70)}!important;color:{side_text}!important;}}
[data-testid="stMetric"],.page-head,.quick-card,[data-testid="stDataFrame"],[data-testid="stExpander"]{{background:{_rgba(card,float(s.get('card_opacity',.97)))}!important;border-color:{line}!important;border-radius:{radius}px!important;backdrop-filter:blur({max(0,int(s.get('background_blur',0) or 0))}px);}}
.premium-hero{{background:linear-gradient(135deg,{hero1} 0%,{hero2} 72%,{_mix(hero2,accent,.78)} 100%)!important;border-radius:{radius+6}px!important;}}
.page-title,.section-title,[data-testid="stMetricValue"]{{color:{ink}!important;}}
.page-sub,.section-sub,[data-testid="stMetricLabel"]{{color:{muted}!important;}}
.stButton>button{{border-radius:{max(6,radius-3)}px!important;}}
.stButton>button[kind="primary"]{{background:linear-gradient(135deg,{primary},{primary2})!important;border-color:{primary}!important;color:white!important;}}
.status-chip.good{{background:{_mix(success,'#FFFFFF',.10)}!important;border-color:{_mix(success,'#FFFFFF',.25)}!important;color:{success}!important;}}
.status-chip.warn{{background:{_mix(warning,'#FFFFFF',.10)}!important;border-color:{_mix(warning,'#FFFFFF',.25)}!important;color:{warning}!important;}}
.status-chip.bad{{background:{_mix(danger,'#FFFFFF',.10)}!important;border-color:{_mix(danger,'#FFFFFF',.25)}!important;color:{danger}!important;}}
@media (max-width: 768px){{
  .block-container{{padding-top:.55rem!important;padding-left:.55rem!important;padding-right:.55rem!important;}}
  .premium-hero{{padding:18px 16px!important;border-radius:14px!important;}}
  .premium-title{{font-size:1.35rem!important;}}
  .premium-sub{{font-size:.82rem!important;}}
  .page-head{{padding:14px 14px!important;}}
  .page-title{{font-size:1.22rem!important;}}
  [data-testid="stMetric"]{{padding:10px 11px!important;}}
  [data-testid="stMetricValue"]{{font-size:1.08rem!important;}}
  .stButton>button{{min-height:44px!important;}}
}}
</style>'''


def settings_summary(settings=None):
    s=load_ui_settings() if settings is None else settings
    return {
        'Theme':s.get('theme_preset'),
        'Background':s.get('background_mode'),
        'Density':s.get('density'),
        'Default page':s.get('default_page'),
    }
