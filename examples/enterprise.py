"""Example enterprise network: DMZ web -> app -> DB (crown jewel), plus file server and AD."""
from abt import Asset, AttackGoal, Host, LegitFlow, Network, Service
from abt.model import Vuln


def build():
    H = lambda n, z, *svcs: Host(n, z, {s.port: s for s in svcs})
    hosts = {
        "web": H("web", "dmz", Service("http", 80, [Vuln("CVE-WEB-1", 0.8, 6, "user"), Vuln("CVE-WEB-2", 0.4, 8, "root")])),
        "app": H("app", "internal", Service("tomcat", 8080, [Vuln("CVE-APP-1", 0.6, 7, "user")]),
                 Service("ssh", 22, [Vuln("CVE-SSH-1", 0.3, 9, "root")])),
        "db": H("db", "internal", Service("mysql", 3306, [Vuln("CVE-DB-1", 0.5, 9, "root")]),
                Service("ssh", 22, [Vuln("CVE-SSH-2", 0.2, 9, "root")])),
        "files": H("files", "internal", Service("smb", 445, [Vuln("CVE-SMB-1", 0.7, 7, "user")])),
        "ad": H("ad", "internal", Service("ldap", 389, [Vuln("CVE-AD-1", 0.3, 9, "root")])),
    }
    flows = {("web", "app", 8080), ("web", "files", 445), ("app", "db", 3306), ("app", "db", 22),
             ("app", "ad", 389), ("files", "db", 3306), ("files", "ad", 389), ("web", "app", 22)}
    assets = [
        Asset("customer_db", "db", value=10, min_availability=0.9),
        Asset("web_service", "web", value=6, kind="service", min_availability=0.9),
        Asset("domain_admin", "ad", value=8, kind="privilege", min_availability=0.5),
    ]
    legit = [
        LegitFlow("users->web", "ext_users", "web", 80, 5),   # external users; always allowed
        LegitFlow("web->app", "web", "app", 8080, 4),
        LegitFlow("app->db", "app", "db", 3306, 4),
        LegitFlow("app->ad auth", "app", "ad", 389, 2),
    ]
    net = Network(hosts, flows, assets, legit, entry_points=["web"])
    net.hosts["ext_users"] = Host("ext_users", "internet")
    net.flows.add(("ext_users", "web", 80))
    # the pseudo-host above stands for external users; remove it as an attack source
    net.entry_points = ["web"]
    goals = [AttackGoal("exfiltrate", "db", "root", "customer_db"),
             AttackGoal("escalate", "ad", "root", "domain_admin")]
    return net, goals
