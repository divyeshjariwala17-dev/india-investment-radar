from __future__ import annotations
from pathlib import Path
import sys, json, py_compile, ast, importlib, inspect
from backup_manager import create_backup, restore_backup, latest_backup

BASE=Path(__file__).resolve().parent

def _module_info(path: Path):
    tree=ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    names=set(); funcs={}
    for n in tree.body:
        if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)):
            names.add(n.name)
            pos=list(n.args.posonlyargs)+list(n.args.args)
            req=len(pos)-len(n.args.defaults)
            funcs[n.name]={
                'required':[a.arg for a in pos[:req]],
                'all':[a.arg for a in pos],
                'vararg':bool(n.args.vararg)
            }
        elif isinstance(n,ast.ClassDef):
            names.add(n.name)
        elif isinstance(n,ast.Assign):
            for t in n.targets:
                if isinstance(t,ast.Name): names.add(t.id)
        elif isinstance(n,ast.AnnAssign) and isinstance(n.target,ast.Name):
            names.add(n.target.id)
        elif isinstance(n,ast.Import):
            for a in n.names: names.add(a.asname or a.name.split('.')[0])
        elif isinstance(n,ast.ImportFrom):
            for a in n.names: names.add(a.asname or a.name)
    return names,funcs

def _check_calls(app_path, modules):
    issues=[]
    tree=ast.parse(app_path.read_text(encoding='utf-8'), filename=str(app_path))
    imports={}
    for n in tree.body:
        if isinstance(n,ast.ImportFrom) and n.level==0 and n.module in modules:
            for a in n.names:
                imports[a.asname or a.name]=(n.module,a.name)

    cache={}
    for node in ast.walk(tree):
        if not isinstance(node,ast.Call) or not isinstance(node.func,ast.Name):
            continue
        local=node.func.id
        if local not in imports:
            continue
        mod,fn=imports[local]
        if mod not in cache:
            cache[mod]=_module_info(modules[mod])[1]
        sig=cache[mod].get(fn)
        if not sig:
            continue
        given_pos=len(node.args)
        kw={k.arg for k in node.keywords if k.arg}
        missing=[]
        for i,arg in enumerate(sig['required']):
            if i < given_pos or arg in kw:
                continue
            missing.append(arg)
        if missing:
            issues.append(f"line {getattr(node,'lineno','?')}: {mod}.{fn} missing {missing}")
    return issues

def verify():
    bad=[]; checked=0
    modules={p.stem:p for p in BASE.glob('*.py')}

    for p in BASE.glob('*.py'):
        try:
            py_compile.compile(str(p),doraise=True); checked+=1
        except Exception as e:
            bad.append((p.name,f'compile: {e}'))

    try:
        app=BASE/'app.py'
        tree=ast.parse(app.read_text(encoding='utf-8'), filename=str(app))
        cache={}
        for node in ast.walk(tree):
            if isinstance(node,ast.ImportFrom) and node.level==0 and node.module in modules:
                if node.module not in cache:
                    cache[node.module]=_module_info(modules[node.module])[0]
                for a in node.names:
                    if a.name!='*' and a.name not in cache[node.module]:
                        bad.append(('app.py',f'missing import: {node.module}.{a.name}'))
        for issue in _check_calls(app,modules):
            bad.append(('app.py',f'call-signature: {issue}'))
    except Exception as e:
        bad.append(('app.py',f'static QA: {e}'))

    try:
        if str(BASE) not in sys.path:
            sys.path.insert(0,str(BASE))

        pp=importlib.import_module('portfolio_planner')
        for name in ('allocation','scenario_value','future_value','required_monthly_sip','goal_scenarios'):
            if not hasattr(pp,name):
                raise ImportError(f'portfolio_planner missing {name}')

        pe=importlib.import_module('portfolio_engine')
        sig=inspect.signature(pe.read_portfolio)
        p=sig.parameters.get('uploaded')
        if p is None or p.default is inspect._empty:
            raise TypeError('read_portfolio must support no-argument saved portfolio loading')
        saved=pe.read_portfolio()
        if saved is None:
            raise RuntimeError('read_portfolio() returned None')
        mfmod=importlib.import_module('mutual_funds')
        for name in ('refresh_universe','load_universe','refresh_scheme_code','refresh_filtered','refresh_recommended_for_horizon','analyze_cached'):
            if not hasattr(mfmod,name): raise ImportError(f'mutual_funds missing {name}')
        evmod=importlib.import_module('nse_events')
        for name in ('refresh_all_events','load_all_events','action_risk_map','events_for_symbol'):
            if not hasattr(evmod,name): raise ImportError(f'nse_events missing {name}')
    except Exception as e:
        bad.append(('portfolio runtime',str(e)))

    try:
        version=json.loads((BASE/'config.json').read_text(encoding='utf-8')).get('app_version','UNKNOWN')
    except Exception as e:
        version='UNKNOWN'; bad.append(('config.json',str(e)))

    print(f'Version: {version}')
    # Verify update_config has a valid BASE/CONFIG contract.
    try:
        uc=(BASE/'update_config.py').read_text(encoding='utf-8')
        tree_uc=ast.parse(uc, filename=str(BASE/'update_config.py'))
        assigned=set()
        loaded=set()
        for n in ast.walk(tree_uc):
            if isinstance(n,ast.Name):
                if isinstance(n.ctx,ast.Store): assigned.add(n.id)
                elif isinstance(n.ctx,ast.Load): loaded.add(n.id)
        allowed={'Path','json','print','True','False','None'}
        suspicious={x for x in loaded if x.isupper() and x not in assigned and x not in allowed}
        if suspicious:
            bad.append(('update_config.py',f'undefined uppercase globals: {sorted(suspicious)}'))
    except Exception as e:
        bad.append(('update_config.py',f'source check: {e}'))

    print(f'Python modules checked: {checked}')
    if bad:
        print('VERIFY FAILED')
        for n,e in bad: print(f' - {n}: {e}')
        return 1
    print('VERIFY PASS')
    return 0

def main():
    cmd=(sys.argv[1] if len(sys.argv)>1 else 'verify').lower()
    if cmd=='backup':
        p=create_backup(); print(f'BACKUP CREATED: {p}'); return 0
    if cmd in ('restore','restore-latest'):
        r=restore_backup(); print(r.get('message','')); return 0 if r.get('ok') else 1
    if cmd=='latest':
        p=latest_backup(); print(p or 'NO BACKUP'); return 0
    return verify()

if __name__=='__main__':
    raise SystemExit(main())
