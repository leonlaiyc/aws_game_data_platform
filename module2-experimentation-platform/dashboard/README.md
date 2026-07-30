# Central Experiment Operations View

This localhost dashboard solves the original coordination problem: an operator
can see every parallel experiment's site, game, lifecycle state, monitoring
health, exposure SRM status, planned end time, and whether treatment allocation
is still enabled without asking each analyst.

It has no hosting resource or idle AWS cost. The local Python process assumes
the existing operator role and makes SigV4-signed reads to the IAM-protected
registry API; the browser only talks to `127.0.0.1`.

```powershell
python module2-experimentation-platform/dashboard/app.py
```

For a fail-fast preflight without opening a browser:

```powershell
python module2-experimentation-platform/dashboard/app.py --snapshot
```

At team scale, replace this local view with an authenticated internal web
application. Keep the same registry view model; add SSO, owner/team fields,
filters, audit history, and push updates when the number of experiments or
operators makes 15-second polling inefficient.
