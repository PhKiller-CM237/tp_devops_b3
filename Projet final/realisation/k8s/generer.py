"""Manifests publics du projet IC GROUP. Secrets crees par Ansible Vault."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
NS="icgroup"
LABEL={"env":"prod"}
def obj(kind,name,spec=None,api="v1"):
    result={"apiVersion":api,"kind":kind,"metadata":{"name":name,"namespace":NS,"labels":dict(LABEL)}}
    if spec is not None:result["spec"]=spec
    return result
def svc(name,port,target=None,node=None,headless=False):
    spec={"selector":{"app":name},"ports":[{"port":port,"targetPort":target or port}]}
    if node:spec["type"]="NodePort";spec["ports"][0]["nodePort"]=node
    if headless:spec["clusterIP"]="None"
    return obj("Service",name,spec)
def envsecret(name,key):
    return {"name":name,"valueFrom":{"secretKeyRef":{"name":"icgroup-secrets","key":key}}}
def deployment(name,image,count,port,env=None,mounts=None,volumes=None,resources=None):
    labels={"app":name,"env":"prod"}
    container={"name":name,"image":image,"imagePullPolicy":"IfNotPresent","ports":[{"containerPort":port}],"env":env or [],"resources":resources or {"requests":{"cpu":"50m","memory":"64Mi"},"limits":{"cpu":"300m","memory":"192Mi"}}}
    if mounts:container["volumeMounts"]=mounts
    spec={"replicas":count,"selector":{"matchLabels":{"app":name}},"strategy":{"type":"RollingUpdate","rollingUpdate":{"maxUnavailable":0,"maxSurge":1}},"template":{"metadata":{"labels":labels},"spec":{"terminationGracePeriodSeconds":45,"containers":[container]}}}
    if volumes:spec["template"]["spec"]["volumes"]=volumes
    return obj("Deployment",name,spec,"apps/v1")
def pvc(name,size):
    pv=obj("PersistentVolume","icgroup-"+name,{"capacity":{"storage":size},"accessModes":["ReadWriteOnce"],"persistentVolumeReclaimPolicy":"Retain","storageClassName":"icgroup-manual","hostPath":{"path":"/data/icgroup/"+name,"type":"DirectoryOrCreate"}})
    pv["metadata"].pop("namespace")
    claim=obj("PersistentVolumeClaim",name,{"accessModes":["ReadWriteOnce"],"resources":{"requests":{"storage":size}},"storageClassName":"icgroup-manual","volumeName":pv["metadata"]["name"]})
    return [pv,claim]

infra=[]
for name,size in [("postgres-data","2Gi"),("odoo-data","2Gi"),("pgadmin-data","1Gi")]:infra+=pvc(name,size)
postgres=obj("StatefulSet","postgres",{"serviceName":"postgres","replicas":1,"selector":{"matchLabels":{"app":"postgres"}},"template":{"metadata":{"labels":{"app":"postgres","env":"prod"}},"spec":{"containers":[{"name":"postgres","image":"postgres:16-alpine","env":[{"name":"POSTGRES_USER","value":"odoo"},{"name":"POSTGRES_DB","value":"postgres"},envsecret("POSTGRES_PASSWORD","postgres-password"),{"name":"PGDATA","value":"/var/lib/postgresql/data/pgdata"}],"ports":[{"containerPort":5432}],"volumeMounts":[{"name":"data","mountPath":"/var/lib/postgresql/data"}],"readinessProbe":{"exec":{"command":["pg_isready","-U","odoo","-d","postgres"]},"periodSeconds":5},"resources":{"requests":{"cpu":"100m","memory":"128Mi"},"limits":{"cpu":"500m","memory":"384Mi"}}}],"volumes":[{"name":"data","persistentVolumeClaim":{"claimName":"postgres-data"}}]}}},"apps/v1")
infra+=[svc("postgres",5432,headless=True),postgres]
servers={"Servers":{"1":{"Name":"Odoo PostgreSQL","Group":"IC GROUP","Host":"postgres","Port":5432,"MaintenanceDB":"legeni","Username":"odoo","SSLMode":"prefer","PassFile":"/var/lib/pgadmin/.pgpass"}}}
cm=obj("ConfigMap","pgadmin-servers")
cm["data"]={"servers.json":json.dumps(servers),"set_admin.py":"import os\nenv['res.users'].search([('login', '=', 'admin')], limit=1).write({'password': os.environ['ODOO_ADMIN_PASSWORD']})\nenv.cr.commit()\n"}
infra.append(cm)

odoo=deployment("odoo","odoo:18.0",2,8069,env=[{"name":"HOST","value":"postgres"},{"name":"USER","value":"odoo"},envsecret("PASSWORD","postgres-password"),envsecret("ODOO_ADMIN_PASSWORD","odoo-admin-password")],mounts=[{"name":"data","mountPath":"/var/lib/odoo"},{"name":"config","mountPath":"/etc/odoo/odoo.conf","subPath":"odoo.conf","readOnly":True}],volumes=[{"name":"data","persistentVolumeClaim":{"claimName":"odoo-data"}},{"name":"config","secret":{"secretName":"icgroup-secrets","items":[{"key":"odoo.conf","path":"odoo.conf"}]}}],resources={"requests":{"cpu":"100m","memory":"192Mi"},"limits":{"cpu":"700m","memory":"640Mi"}})
ospec=odoo["spec"]["template"]["spec"]
ospec["initContainers"]=[{"name":"volume-owner","image":"busybox:1.36","command":["sh","-c","chown -R 100:101 /var/lib/odoo"],"volumeMounts":[{"name":"data","mountPath":"/var/lib/odoo"}]}]
oc=ospec["containers"][0]
oc["startupProbe"]={"tcpSocket":{"port":8069},"periodSeconds":5,"failureThreshold":120}
oc["readinessProbe"]={"httpGet":{"path":"/web/login","port":8069},"periodSeconds":10,"timeoutSeconds":5}
oc["livenessProbe"]={"tcpSocket":{"port":8069},"periodSeconds":15}

pgadmin=deployment("pgadmin","dpage/pgadmin4:9.19",1,80,env=[{"name":"PGADMIN_DEFAULT_EMAIL","value":"admin@example.com"},envsecret("PGADMIN_DEFAULT_PASSWORD","pgadmin-password"),{"name":"PGADMIN_DISABLE_POSTFIX","value":"1"},{"name":"PGADMIN_REPLACE_SERVERS_ON_STARTUP","value":"True"},{"name":"PGPASS_FILE","value":"/run/secrets/pgpass"}],mounts=[{"name":"data","mountPath":"/var/lib/pgadmin"},{"name":"servers","mountPath":"/pgadmin4/servers.json","subPath":"servers.json","readOnly":True},{"name":"secret","mountPath":"/run/secrets","readOnly":True}],volumes=[{"name":"data","persistentVolumeClaim":{"claimName":"pgadmin-data"}},{"name":"servers","configMap":{"name":"pgadmin-servers","items":[{"key":"servers.json","path":"servers.json"}]}},{"name":"secret","secret":{"secretName":"icgroup-secrets","items":[{"key":"pgpass","path":"pgpass"}]}}],resources={"requests":{"cpu":"100m","memory":"128Mi"},"limits":{"cpu":"500m","memory":"384Mi"}})
pgadmin["spec"]["strategy"]={"type":"Recreate"}
pgadmin["spec"]["template"]["spec"]["initContainers"]=[{"name":"volume-owner","image":"busybox:1.36","command":["sh","-c","chown -R 5050:0 /var/lib/pgadmin"],"volumeMounts":[{"name":"data","mountPath":"/var/lib/pgadmin"}]}]
pc=pgadmin["spec"]["template"]["spec"]["containers"][0]
pc["startupProbe"]={"httpGet":{"path":"/misc/ping","port":80},"periodSeconds":5,"failureThreshold":90}
pc["readinessProbe"]={"httpGet":{"path":"/misc/ping","port":80},"periodSeconds":10,"timeoutSeconds":5}

portal=deployment("ic-webapp","legeni-academy:1.0",2,8080,env=[{"name":"ODOO_URL","value":"http://localhost:8069"},{"name":"PGADMIN_URL","value":"http://localhost:5050"}])
portal["spec"]["template"]["spec"]["securityContext"]={"runAsNonRoot":True,"runAsUser":10001}
portal["spec"]["template"]["spec"]["containers"][0]["readinessProbe"]={"httpGet":{"path":"/health","port":8080},"periodSeconds":5,"timeoutSeconds":3}
apps=[odoo,svc("odoo",8069,node=31669),pgadmin,svc("pgadmin",80,node=31550),portal,svc("ic-webapp",8080,node=31995)]

job=obj("Job","odoo-init",{"backoffLimit":1,"template":{"metadata":{"labels":{"env":"prod","app":"odoo-init"}},"spec":{"restartPolicy":"Never","initContainers":[{"name":"volume-owner","image":"busybox:1.36","command":["sh","-c","chown -R 100:101 /var/lib/odoo"],"volumeMounts":[{"name":"data","mountPath":"/var/lib/odoo"}]}],"containers":[{"name":"init","image":"odoo:18.0","command":["sh","-ec"],"args":["/entrypoint.sh odoo --stop-after-init -d legeni -i base --without-demo=all\n/entrypoint.sh odoo shell -d legeni --no-http < /opt/icgroup/set_admin.py\n"],"env":[{"name":"HOST","value":"postgres"},{"name":"USER","value":"odoo"},envsecret("PASSWORD","postgres-password"),envsecret("ODOO_ADMIN_PASSWORD","odoo-admin-password")],"volumeMounts":[{"name":"data","mountPath":"/var/lib/odoo"},{"name":"config","mountPath":"/etc/odoo/odoo.conf","subPath":"odoo.conf","readOnly":True},{"name":"script","mountPath":"/opt/icgroup","readOnly":True}],"resources":{"requests":{"cpu":"200m","memory":"256Mi"},"limits":{"cpu":"1","memory":"768Mi"}}}],"volumes":[{"name":"data","persistentVolumeClaim":{"claimName":"odoo-data"}},{"name":"config","secret":{"secretName":"icgroup-secrets","items":[{"key":"odoo.conf","path":"odoo.conf"}]}},{"name":"script","configMap":{"name":"pgadmin-servers","items":[{"key":"set_admin.py","path":"set_admin.py"}]}}]}}},"batch/v1")

for name,objects in [("10-infra.json",infra),("20-apps.json",apps),("15-odoo-init.json",[job])]:
    (ROOT/name).write_text(json.dumps({"apiVersion":"v1","kind":"List","items":objects},indent=2)+"\n")
print("Manifests generated:",len(infra),"infra objects,",len(apps),"application objects, 1 Job")
