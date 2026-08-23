import { useState, type FormEvent, useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { AxiosError } from "axios";
import { AlertCircle, Loader2 } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/hooks/useAuth";

interface LocationState {
  from?: { pathname?: string };
}

export function LoginForm() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [employeeId, setEmployeeId] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [lockoutTimer, setLockoutTimer] = useState<number | null>(null);

  const redirectTo = (location.state as LocationState | null)?.from?.pathname ?? "/dashboard";

  useEffect(() => {
    const lockoutUntil = localStorage.getItem("loginLockoutUntil");
    if (lockoutUntil) {
      const remainingTime = Math.max(0, parseInt(lockoutUntil, 10) - Date.now());
      if (remainingTime > 0) {
        setLockoutTimer(remainingTime);
      } else {
        localStorage.removeItem("loginLockoutUntil");
        localStorage.removeItem("loginAttempts");
      }
    }
  }, []);

  useEffect(() => {
    if (lockoutTimer !== null && lockoutTimer > 0) {
      const timerId = setTimeout(() => {
        setLockoutTimer((prev) => (prev !== null ? prev - 1000 : null));
      }, 1000);
      return () => clearTimeout(timerId);
    } else if (lockoutTimer !== null && lockoutTimer <= 0) {
      localStorage.removeItem("loginLockoutUntil");
      localStorage.removeItem("loginAttempts");
      setLockoutTimer(null);
      setError(null);
    }
  }, [lockoutTimer]);

  const isLockedOut = lockoutTimer !== null && lockoutTimer > 0;
  const lockoutMinutes = isLockedOut ? Math.ceil(lockoutTimer / 60000) : 0;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (isLockedOut) return;

    setError(null);
    setIsSubmitting(true);

    try {
      await login({ employee_id: employeeId, password });
      localStorage.removeItem("loginAttempts");
      localStorage.removeItem("loginLockoutUntil");
      navigate(redirectTo, { replace: true });
    } catch (err) {
      const currentAttempts = parseInt(localStorage.getItem("loginAttempts") || "0", 10) + 1;
      localStorage.setItem("loginAttempts", currentAttempts.toString());
      
      if (currentAttempts >= 5) {
        const lockoutTime = Date.now() + 15 * 60 * 1000;
        localStorage.setItem("loginLockoutUntil", lockoutTime.toString());
        setLockoutTimer(15 * 60 * 1000);
        setError("Too many failed attempts. Please try again in 15 minutes.");
        setIsSubmitting(false);
        return;
      }

      if (err instanceof AxiosError) {
        const data = err.response?.data as { detail?: string | Array<{ msg?: string }> } | undefined;
        const detail = data?.detail;
        if (typeof detail === "string") {
          setError(detail);
        } else if (Array.isArray(detail) && detail.length > 0 && typeof detail[0]?.msg === "string") {
          setError(detail[0].msg);
        } else {
          setError("Login failed");
        }
      } else {
        setError("Login failed");
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-5" noValidate>
      {error && !isLockedOut && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Sign-in failed</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {isLockedOut && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Account locked</AlertTitle>
          <AlertDescription>
            Too many failed attempts. Please try again in {lockoutMinutes} minute{lockoutMinutes === 1 ? "" : "s"}.
          </AlertDescription>
        </Alert>
      )}

      <div className="space-y-2">
        <Label htmlFor="employee_id">Employee ID</Label>
        <Input
          id="employee_id"
          name="employee_id"
          autoComplete="username"
          placeholder="EMP-0042"
          value={employeeId}
          onChange={(e) => setEmployeeId(e.target.value)}
          required
          autoFocus
          disabled={isLockedOut}
        />
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Label htmlFor="password">Password</Label>
          <a href="/forgot-password" className="text-sm font-medium text-primary hover:underline">
            Forgot password?
          </a>
        </div>
        <Input
          id="password"
          name="password"
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          minLength={8}
          disabled={isLockedOut}
        />
      </div>

      <Button type="submit" className="w-full" disabled={isSubmitting || isLockedOut}>
        {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
        Sign in
      </Button>
    </form>
  );
}
