from __future__ import annotations
from pathlib import Path
from getpass import getpass
import os, sys

BASE=Path(__file__).resolve().parent
ENV=BASE/'.env'

def main():
    print('\nINDIA INVESTMENT RADAR — CONNECT PC TO SUPABASE\n')
    print('Use the SAME Supabase project already used by your online Radar.')
    print('The secret key is hidden while you type/paste it.\n')
    url=input('Supabase Project URL (https://....supabase.co): ').strip().rstrip('/')
    key=getpass('Supabase Secret Key (sb_secret_...): ').strip()
    bucket=input('Bucket name [radar-private]: ').strip() or 'radar-private'
    if not (url.startswith('https://') and '.supabase.co' in url):
        print('ERROR: Project URL does not look correct. Nothing was saved.');return 1
    if not (key.startswith('sb_secret_') or key.startswith('eyJ')):
        print('ERROR: Secret key does not look correct. Nothing was saved.');return 1
    # Quote values defensively; never print the secret back.
    text=f'SUPABASE_URL="{url}"\nSUPABASE_SECRET_KEY="{key}"\nSUPABASE_BUCKET="{bucket}"\n'
    ENV.write_text(text,encoding='utf-8')
    try:
        os.chmod(ENV,0o600)
    except Exception:pass
    # Load saved values into this process and test.
    os.environ['SUPABASE_URL']=url;os.environ['SUPABASE_SECRET_KEY']=key;os.environ['SUPABASE_BUCKET']=bucket
    try:
        from cloud_sync import test_connection
        r=test_connection()
        if r.get('ok'):
            print('\nCONNECTED:',r.get('message'))
            print('PC cloud sync is ready. Open Radar and use Maintenance -> Full Data Setup / Repair.')
            return 0
        print('\nSAVED, BUT CONNECTION TEST FAILED:',r.get('message'))
        print('Check the URL/key/bucket and run this setup again.')
        return 2
    except Exception as e:
        print('\nSAVED, BUT CONNECTION TEST COULD NOT RUN:',e)
        return 2

if __name__=='__main__':raise SystemExit(main())
