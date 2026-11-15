"""Prepare le projet final sans exposer de secret."""
from pathlib import Path
import json
import secrets
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parent.parent
STATE=Path.home()/".local/state/devops-tps"
CONTROL="/tmp/devops-tps-final"
KEY=Path.home()/".local/state/legeni/vault-pass"

def command(args,name,private=False,data=None,timeout=1200):
    result=subprocess.run(args,input=data,text=True,capture_output=True,timeout=timeout)
    path=ROOT/"preuves"/(name+".log")
    path.write_text("<operation privee>\n" if private else result.stdout+result.stderr)
    if result.returncode: raise RuntimeError(name+" failed; see "+str(path))
    print("OK",name,flush=True)
    return result.stdout

def sync():
    command(["docker","cp",str(ROOT)+"/.","jenkins:"+CONTROL+"/"],"sync")
    command(["docker","cp",str(KEY),"jenkins:/tmp/icgroup-vault-pass"],"copy-vault-key",private=True)

def prepare():
    STATE.mkdir(exist_ok=True)
    path=STATE/"icgroup-secrets.json"
    if path.exists(): values=json.loads(path.read_text())
    else:
        values={name:secrets.token_urlsafe(30) for name in ["vault_postgres_password","vault_pgadmin_password","vault_odoo_master_password","vault_odoo_admin_password"]}
        path.write_text(json.dumps(values));path.chmod(0o600)
    vault=ROOT/"ansible/vars/vault.yml"
    command(["docker","cp",str(KEY),"jenkins:/tmp/icgroup-vault-pass"],"prepare-vault-key",private=True)
    if not vault.exists():
        command(["docker","exec","-i","jenkins","sh","-c","umask 077; cat > /tmp/icgroup-plaintext"],"create-secret-buffer",private=True,data=json.dumps(values))
        command(["docker","exec","jenkins","ansible-vault","encrypt","--vault-password-file","/tmp/icgroup-vault-pass","--output","/tmp/icgroup-encrypted","/tmp/icgroup-plaintext"],"encrypt-vault",private=True)
        command(["docker","cp","jenkins:/tmp/icgroup-encrypted",str(vault)],"copy-encrypted-vault",private=True)
        command(["docker","exec","jenkins","rm","-f","/tmp/icgroup-plaintext"],"remove-secret-buffer",private=True)
    access=STATE/"icgroup-acces.txt"
    access.write_text("Odoo : http://localhost:8069\nUtilisateur : admin\nMot de passe : "+values["vault_odoo_admin_password"]+"\n\npgAdmin : http://localhost:5050\nUtilisateur : admin@example.com\nMot de passe : "+values["vault_pgadmin_password"]+"\n")
    access.chmod(0o600)
    # File credentials are constructed dynamically; no contents are saved in the repository.
    sys.path.insert(0,str(REPO/"TP_jenkins/realisation"))
    from jenkins_api import groovy
    script="""import com.cloudbees.plugins.credentials.*
import com.cloudbees.plugins.credentials.domains.Domain
import org.jenkinsci.plugins.plaincredentials.impl.FileCredentialsImpl
import com.cloudbees.plugins.credentials.SecretBytes
def p=SystemCredentialsProvider.getInstance()
def s=p.getStore()
"""
    sources=[("ansible-vault-pass",KEY),("ansible-ssh-key",REPO/"TP ansible/lab/keys/id_ansible"),("kubeconfig",Path.home()/".local/state/legeni/kubeconfig-jenkins.json")]
    import base64
    for cid,source in sources:
        encoded=base64.b64encode(source.read_bytes()).decode()
        script+="if (!p.getCredentials().any { it.id == '"+cid+"' }) { s.addCredentials(Domain.global(),new FileCredentialsImpl(CredentialsScope.GLOBAL,'"+cid+"','TP DevOps',"+json.dumps(source.name)+",SecretBytes.fromBytes("+json.dumps(encoded)+".decodeBase64()))) }\n"
    script+="println 'File credentials configured'"
    print(groovy(script).strip(),flush=True)
    shutil.copy2(ROOT/"releases.txt",ROOT/"portal/releases.txt")
    command(["docker","build","--target","test","-t","legeni-academy:test",str(ROOT/"portal")],"portal-tests")
    version=dict(line.split(None,1) for line in (ROOT/"releases.txt").read_text().splitlines())["VERSION"]
    command(["docker","build","--build-arg","APP_VERSION="+version,"-t","legeni-academy:"+version,str(ROOT/"portal")],"portal-build")
    subprocess.run(["docker","rm","-f","test-legeni-academy"],capture_output=True)
    command(["docker","run","-d","--name","test-legeni-academy","-e","ODOO_URL=https://www.odoo.com/","-e","PGADMIN_URL=https://www.pgadmin.org/","legeni-academy:"+version],"portal-test-start")
    import time
    for _ in range(30):
        result=subprocess.run(["docker","exec","test-legeni-academy","python","-c","import urllib.request; urllib.request.urlopen('http://localhost:8080/health')"],capture_output=True)
        if result.returncode==0:break
        time.sleep(1)
    html=command(["docker","exec","test-legeni-academy","python","-c","import urllib.request; print(urllib.request.urlopen('http://localhost:8080/').read().decode())"],"portal-acceptance")
    assert "https://www.odoo.com/" in html and "https://www.pgadmin.org/" in html
    command(["docker","rm","-f","test-legeni-academy"],"portal-test-cleanup")
    sync()
    for book in ["provision.yml","load-images.yml","deploy-docker.yml","deploy-k8s.yml","gateway.yml"]:
        command(["docker","exec","-w",CONTROL+"/ansible","jenkins","ansible-playbook",book,"--syntax-check","--vault-password-file","/tmp/icgroup-vault-pass"],"syntax-"+book.replace(".yml",""))
    print("Project prepared; access information stored privately in",str(access),flush=True)

if __name__=="__main__":
    prepare()
