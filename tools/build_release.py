"""Build a candidate wheel and provenance manifest through normal PEP 517."""
from pathlib import Path
import argparse, hashlib, json, subprocess, sys, zipfile

def build_release(output):
    root=Path(__file__).resolve().parents[1]
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False)
    def git(*args):return subprocess.check_output(['git','-C',str(root),*args],text=True).strip()
    sha=git('rev-parse','HEAD');dirty=bool(git('status','--porcelain'))
    subprocess.run([sys.executable,'-m','pip','wheel','--no-deps','--no-build-isolation','-w',str(output),str(root)],check=True)
    wheel=next(output.glob('*.whl'))
    with zipfile.ZipFile(wheel) as z:
        names=z.namelist()
        required=['deck_master/resources/skill/SKILL.md','deck_master/resources/static/app.js']
        required += ['deck_master/resources/contracts/'+name+'.schema.json' for name in ('document.v1','page.v2','artifact.v1','task.v1','review.v1')]
        for name in required:
            if name not in names:raise RuntimeError('missing resource: '+name)
        if any(name.startswith(('runtime/','workflow/','high_density/','preview/','build/')) for name in names):raise RuntimeError('legacy package in wheel')
        files={name:hashlib.sha256(z.read(name)).hexdigest() for name in sorted(names) if not name.endswith('/')}
    manifest={'release_id':sha[:12]+'-'+hashlib.sha256(wheel.read_bytes()).hexdigest()[:12], 'source_sha':sha,'source_dirty':dirty,'wheel':wheel.name,'wheel_sha256':hashlib.sha256(wheel.read_bytes()).hexdigest(),'files':files,'entry':['python','-m','deck_master'],'professional_evidence':'not_evaluated'}
    (output/'release.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',required=True)
    print(json.dumps(build_release(parser.parse_args().out),indent=2))
