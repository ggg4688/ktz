import { useEffect, useState } from "react";
import { Settings2, ShieldCheck, UserPlus, Users } from "lucide-react";

import { useAuth } from "@/contexts/AuthContext";
import {
  createUser,
  getHealthModel,
  listUsers,
  updateHealthModel,
  type HealthModelConfig,
  type PublicUser,
  type RoleName,
} from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

export default function Admin() {
  const { token } = useAuth();
  const [config, setConfig] = useState<HealthModelConfig | null>(null);
  const [users, setUsers] = useState<PublicUser[]>([]);
  const [jsonValue, setJsonValue] = useState("");
  const [pendingConfig, setPendingConfig] = useState(true);
  const [pendingUser, setPendingUser] = useState(false);
  const [configMessage, setConfigMessage] = useState("");
  const [userMessage, setUserMessage] = useState("");
  const [newUser, setNewUser] = useState({
    username: "",
    full_name: "",
    password: "",
    role: "viewer" as RoleName,
  });

  useEffect(() => {
    const loadAdminData = async () => {
      if (!token) {
        return;
      }
      setPendingConfig(true);
      setConfigMessage("");
      setUserMessage("");
      try {
        const [currentConfig, currentUsers] = await Promise.all([
          getHealthModel(token),
          listUsers(token),
        ]);
        setConfig(currentConfig);
        setUsers(currentUsers);
        setJsonValue(JSON.stringify(currentConfig, null, 2));
      } catch (err) {
        setConfigMessage(err instanceof Error ? err.message : "Failed to load admin data");
      } finally {
        setPendingConfig(false);
      }
    };

    loadAdminData();
  }, [token]);

  const handleReload = async () => {
    if (!token) {
      return;
    }
    setPendingConfig(true);
    setConfigMessage("");
    try {
      const [currentConfig, currentUsers] = await Promise.all([
        getHealthModel(token),
        listUsers(token),
      ]);
      setConfig(currentConfig);
      setUsers(currentUsers);
      setJsonValue(JSON.stringify(currentConfig, null, 2));
    } catch (err) {
      setConfigMessage(err instanceof Error ? err.message : "Failed to reload config");
    } finally {
      setPendingConfig(false);
    }
  };

  const handleSave = async () => {
    if (!token) {
      return;
    }

    setPendingConfig(true);
    setConfigMessage("");
    try {
      const parsed = JSON.parse(jsonValue) as HealthModelConfig;
      const updated = await updateHealthModel(token, parsed);
      setConfig(updated);
      setJsonValue(JSON.stringify(updated, null, 2));
      setConfigMessage(`Saved health model version ${updated.health_model_version}`);
    } catch (err) {
      setConfigMessage(err instanceof Error ? err.message : "Failed to save config");
    } finally {
      setPendingConfig(false);
    }
  };

  const handleCreateUser = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!token) {
      return;
    }

    setPendingUser(true);
    setUserMessage("");
    try {
      const createdUser = await createUser(token, {
        username: newUser.username,
        password: newUser.password,
        full_name: newUser.full_name || undefined,
        role: newUser.role,
      });
      setUsers((currentUsers) =>
        [...currentUsers, createdUser].sort((left, right) => left.username.localeCompare(right.username)),
      );
      setNewUser({
        username: "",
        full_name: "",
        password: "",
        role: "viewer",
      });
      setUserMessage(`Created user ${createdUser.username}`);
    } catch (err) {
      setUserMessage(err instanceof Error ? err.message : "Failed to create user");
    } finally {
      setPendingUser(false);
    }
  };

  return (
    <div className="space-y-6 p-6">
      <section className="rounded-3xl border border-border/70 bg-[linear-gradient(135deg,hsl(var(--card)),hsl(222_44%_8%))] p-6 shadow-xl shadow-black/10">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-3">
              <Badge variant="secondary" className="gap-2">
                <ShieldCheck className="h-3.5 w-3.5" />
                Admin only
              </Badge>
              {config ? <Badge variant="outline">Model version {config.health_model_version}</Badge> : null}
            </div>
            <div>
              <h1 className="text-3xl font-semibold tracking-tight">Health model administration</h1>
              <p className="max-w-3xl text-sm leading-6 text-muted-foreground">
                Inspect and edit the live health-index configuration stored in the backend database.
              </p>
            </div>
          </div>
          <div className="flex flex-wrap gap-3">
            <Button variant="secondary" onClick={handleReload} disabled={pendingConfig}>
              Reload
            </Button>
            <Button onClick={handleSave} disabled={pendingConfig}>
              Save model
            </Button>
          </div>
        </div>

        {configMessage ? (
          <p className="mt-4 rounded-xl border border-border/80 bg-secondary/40 px-4 py-3 text-sm text-muted-foreground">
            {configMessage}
          </p>
        ) : null}
      </section>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,0.9fr)_minmax(320px,1.1fr)]">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <UserPlus className="h-4 w-4" />
              Create user
            </CardTitle>
            <CardDescription>
              Add new backend users directly to the RBAC database.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form className="space-y-4" onSubmit={handleCreateUser}>
              <Input
                value={newUser.username}
                onChange={(event) => setNewUser((current) => ({ ...current, username: event.target.value }))}
                placeholder="Username"
                className="bg-secondary/40"
                disabled={pendingUser}
              />
              <Input
                value={newUser.full_name}
                onChange={(event) => setNewUser((current) => ({ ...current, full_name: event.target.value }))}
                placeholder="Full name"
                className="bg-secondary/40"
                disabled={pendingUser}
              />
              <Input
                type="password"
                value={newUser.password}
                onChange={(event) => setNewUser((current) => ({ ...current, password: event.target.value }))}
                placeholder="Password"
                className="bg-secondary/40"
                disabled={pendingUser}
              />
              <label className="space-y-2 text-sm">
                <span className="text-muted-foreground">Role</span>
                <select
                  value={newUser.role}
                  onChange={(event) =>
                    setNewUser((current) => ({ ...current, role: event.target.value as RoleName }))
                  }
                  className="flex h-10 w-full rounded-md border border-input bg-secondary/40 px-3 py-2 text-sm"
                  disabled={pendingUser}
                >
                  <option value="viewer">viewer</option>
                  <option value="operator">operator</option>
                  <option value="admin">admin</option>
                </select>
              </label>
              <Button type="submit" disabled={pendingUser} className="w-full">
                {pendingUser ? "Creating..." : "Create user"}
              </Button>
            </form>

            {userMessage ? (
              <p className="mt-4 rounded-xl border border-border/80 bg-secondary/40 px-4 py-3 text-sm text-muted-foreground">
                {userMessage}
              </p>
            ) : null}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Users className="h-4 w-4" />
              Backend users
            </CardTitle>
            <CardDescription>
              Current accounts stored in the backend database.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {users.map((user) => (
              <div
                key={user.username}
                className="flex items-center justify-between gap-4 rounded-xl border border-border/80 bg-secondary/20 p-4"
              >
                <div>
                  <p className="font-medium">{user.username}</p>
                  <p className="text-sm text-muted-foreground">{user.full_name}</p>
                </div>
                <Badge variant={user.role === "admin" ? "default" : "secondary"}>{user.role}</Badge>
              </div>
            ))}
            {!users.length ? <p className="text-sm text-muted-foreground">No users loaded.</p> : null}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.4fr)_minmax(320px,0.8fr)]">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Settings2 className="h-4 w-4" />
              Health model JSON
            </CardTitle>
            <CardDescription>
              Edit the same config that powers the backend score formula and alert thresholds.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Textarea
              value={jsonValue}
              onChange={(event) => setJsonValue(event.target.value)}
              className="min-h-[520px] bg-secondary/40 font-mono text-xs leading-6"
              spellCheck={false}
              disabled={pendingConfig}
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Model summary</CardTitle>
            <CardDescription>Quick readout of the most important configuration levers.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {config ? (
              <>
                <div className="rounded-xl border border-border/80 p-4">
                  <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">Formula</p>
                  <p className="mt-2 text-sm leading-6 text-muted-foreground">{config.formula}</p>
                </div>

                <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
                  <div className="rounded-xl border border-border/80 p-4">
                    <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">Thresholds</p>
                    <p className="mt-2 text-sm">Normal from {config.categories.normal_min}</p>
                    <p className="text-sm">Attention from {config.categories.attention_min}</p>
                  </div>
                  <div className="rounded-xl border border-border/80 p-4">
                    <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">Alert penalties</p>
                    <p className="mt-2 text-sm">Warning {config.severity_penalties.warning}</p>
                    <p className="text-sm">Critical {config.severity_penalties.critical}</p>
                    <p className="text-sm">Cap {config.alert_penalty_cap}</p>
                  </div>
                </div>

                <div className="space-y-3">
                  {Object.entries(config.metrics).map(([key, metric]) => (
                    <div key={key} className="rounded-xl border border-border/80 bg-secondary/20 p-4">
                      <div className="flex items-center justify-between gap-3">
                        <p className="font-medium">{metric.label}</p>
                        <Badge variant="outline">{metric.weight}</Badge>
                      </div>
                      <p className="mt-2 text-xs uppercase tracking-[0.2em] text-muted-foreground">
                        {key.replaceAll("_", " ")}
                      </p>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <p className="text-sm text-muted-foreground">Health model not loaded yet.</p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
