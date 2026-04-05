import { useState } from "react";
import { ApiError, useAuth } from "@/contexts/AuthContext";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { KeyRound, Train } from "lucide-react";

export default function Login() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setPending(true);
    setError("");

    try {
      await login(username, password);
      navigate("/");
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Login failed");
      }
    } finally {
      setPending(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-[radial-gradient(circle_at_top,hsl(var(--primary)/0.22),transparent_38%),linear-gradient(180deg,hsl(222_47%_5%),hsl(222_47%_7%))] p-4">
      <Card className="w-full max-w-md border-border/80 bg-card/95 shadow-2xl shadow-black/25">
        <CardHeader className="space-y-4 text-center">
          <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl border border-primary/20 bg-primary/10">
            <Train className="h-8 w-8 text-primary" />
          </div>
          <div className="space-y-2">
            <Badge variant="secondary" className="mx-auto inline-flex gap-2 border-primary/20 bg-primary/10 text-primary">
              <KeyRound className="h-3.5 w-3.5" />
              Backend JWT Session
            </Badge>
            <CardTitle className="text-2xl">Locomotive Digital Twin</CardTitle>
            <CardDescription>
              Sign in with a backend account to open the live telemetry dashboard.
            </CardDescription>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <form onSubmit={handleSubmit} className="space-y-4">
            <Input
              placeholder="Username"
              value={username}
              onChange={e => setUsername(e.target.value)}
              className="bg-secondary/70"
              disabled={pending}
            />
            <Input
              type="password"
              placeholder="Password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              className="bg-secondary/70"
              disabled={pending}
            />
            {error && <p className="text-sm text-destructive">{error}</p>}
            <Button type="submit" className="w-full" disabled={pending}>
              {pending ? "Signing in..." : "Sign In"}
            </Button>
          </form>

          <div className="rounded-xl border border-border/80 bg-secondary/40 p-4 text-sm text-muted-foreground">
            <p className="font-medium text-foreground">Demo accounts</p>
            <p>`admin / admin123`</p>
            <p>`operator / operator123`</p>
            <p>`viewer / viewer123`</p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
