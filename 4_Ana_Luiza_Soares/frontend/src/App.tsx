import { useCallback, useEffect, useMemo, useState } from "react";
import { HomePage } from "./pages/HomePage";
import { DisciplinesPage } from "./pages/DisciplinesPage";
import { DisciplineDetailPage } from "./pages/DisciplineDetailPage";
import { StudyPlanPage } from "./pages/StudyPlanPage";
import { MatriculaImportPage } from "./pages/MatriculaImportPage";
import { CalendarPage } from "./pages/CalendarPage";
import { PublicLandingPage } from "./pages/PublicLandingPage";
import { LoginPage } from "./pages/LoginPage";
import { RegisterPage } from "./pages/RegisterPage";
import { AppShell } from "./components/AppShell";
import { getMe, logout, type AuthUser } from "./api/client";

type Route =
  | { page: "landing" }
  | { page: "login" }
  | { page: "register" }
  | { page: "home" }
  | { page: "disciplines" }
  | { page: "discipline"; id: string }
  | { page: "study-plan" }
  | { page: "calendar" }
  | { page: "matricula-import" };

const RETURN_PATH_KEY = "estudaunb_return_path";

function routeFromPath(rawPath: string): Route {
  const path = rawPath.length > 1 ? rawPath.replace(/\/+$/, "") : rawPath;
  if (path === "/") return { page: "landing" };
  if (path === "/login") return { page: "login" };
  if (path === "/register") return { page: "register" };
  if (path === "/app") return { page: "home" };
  if (path === "/disciplines") return { page: "disciplines" };
  if (path.startsWith("/disciplines/")) {
    const id = path.split("/")[2];
    if (id) return { page: "discipline", id: decodeURIComponent(id) };
  }
  if (path === "/study-plan") return { page: "study-plan" };
  if (path === "/calendar") return { page: "calendar" };
  if (path === "/matricula-import") return { page: "matricula-import" };
  return { page: "landing" };
}

function parseLocation(): Route {
  const legacyHash = window.location.hash.replace(/^#/, "");
  if (window.location.pathname === "/" && legacyHash.startsWith("/"))
    return routeFromPath(legacyHash);
  return routeFromPath(window.location.pathname);
}

function pathFor(route: Route): string {
  if (route.page === "landing") return "/";
  if (route.page === "login") return "/login";
  if (route.page === "register") return "/register";
  if (route.page === "home") return "/app";
  if (route.page === "disciplines") return "/disciplines";
  if (route.page === "discipline")
    return `/disciplines/${encodeURIComponent(route.id)}`;
  if (route.page === "study-plan") return "/study-plan";
  if (route.page === "calendar") return "/calendar";
  return "/matricula-import";
}

function isProtected(route: Route): boolean {
  return !["landing", "login", "register"].includes(route.page);
}

function savedPrivateRoute(): Route | null {
  const value = sessionStorage.getItem(RETURN_PATH_KEY);
  if (!value) return null;
  const route = routeFromPath(value);
  return isProtected(route) ? route : null;
}

export default function App() {
  const [route, setRoute] = useState<Route>(() => parseLocation());
  const [user, setUser] = useState<AuthUser | null>(null);
  const [checkingSession, setCheckingSession] = useState(true);

  const navigate = useCallback((next: Route, replace = false) => {
    const path = pathFor(next);
    window.history[replace ? "replaceState" : "pushState"]({}, "", path);
    setRoute(next);
    window.scrollTo({ top: 0, behavior: "auto" });
  }, []);

  useEffect(() => {
    const onPopState = () => setRoute(parseLocation());
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  useEffect(() => {
    if (!localStorage.getItem("estudaunb_token")) {
      setCheckingSession(false);
      return;
    }
    getMe()
      .then(setUser)
      .catch(() => logout())
      .finally(() => setCheckingSession(false));
  }, []);

  useEffect(() => {
    if (checkingSession) return;
    if (isProtected(route) && !user) {
      sessionStorage.setItem(RETURN_PATH_KEY, pathFor(route));
      navigate({ page: "login" }, true);
      return;
    }
    if (route.page === "login" && user) {
      const destination = savedPrivateRoute() ?? { page: "home" as const };
      sessionStorage.removeItem(RETURN_PATH_KEY);
      navigate(destination, true);
    }
  }, [checkingSession, navigate, route, user]);

  const navigation = useMemo(
    () => ({
      goHome: () => navigate({ page: "home" }),
      goDisciplines: () => navigate({ page: "disciplines" }),
      goDiscipline: (id: string) => navigate({ page: "discipline", id }),
      goStudyPlan: () => navigate({ page: "study-plan" }),
      goCalendar: () => navigate({ page: "calendar" }),
      goMatriculaImport: () => navigate({ page: "matricula-import" }),
    }),
    [navigate],
  );

  function handleLogin(authenticatedUser: AuthUser) {
    setUser(authenticatedUser);
    const destination = savedPrivateRoute() ?? { page: "home" as const };
    sessionStorage.removeItem(RETURN_PATH_KEY);
    navigate(destination, true);
  }

  if (route.page === "landing")
    return (
      <PublicLandingPage
        user={user}
        onLogin={() => navigate({ page: "login" })}
        onRegister={() => navigate({ page: "register" })}
        onDashboard={() => navigate({ page: "home" })}
      />
    );
  if (route.page === "register")
    return (
      <RegisterPage
        onHome={() => navigate({ page: "landing" })}
        onLogin={() => navigate({ page: "login" })}
      />
    );
  if (route.page === "login") {
    if (checkingSession || user)
      return (
        <main className="auth-loading">
          <span className="spinner" aria-hidden="true" />
          <p>Restaurando sessão...</p>
        </main>
      );
    return (
      <LoginPage
        onLogin={handleLogin}
        onHome={() => navigate({ page: "landing" })}
        onRegister={() => navigate({ page: "register" })}
      />
    );
  }
  if (checkingSession || !user)
    return (
      <main className="auth-loading">
        <span className="spinner" aria-hidden="true" />
        <p>
          {checkingSession
            ? "Restaurando sessão..."
            : "Redirecionando para o login..."}
        </p>
      </main>
    );

  return (
    <AppShell
      user={user}
      onLogout={() => {
        logout();
        setUser(null);
        sessionStorage.removeItem(RETURN_PATH_KEY);
        navigate({ page: "landing" }, true);
      }}
      activePage={route.page}
      onNavigate={(page) => navigate({ page })}
    >
      {route.page === "home" && (
        <HomePage
          onOpenDisciplines={navigation.goDisciplines}
          onOpenMatriculaImport={navigation.goMatriculaImport}
          onOpenStudyPlan={navigation.goStudyPlan}
        />
      )}
      {route.page === "disciplines" && (
        <DisciplinesPage onOpenDiscipline={navigation.goDiscipline} />
      )}
      {route.page === "discipline" && (
        <DisciplineDetailPage
          disciplineId={route.id}
          onBack={navigation.goDisciplines}
        />
      )}
      {route.page === "study-plan" && (
        <StudyPlanPage onOpenCalendar={navigation.goCalendar} />
      )}
      {route.page === "calendar" && (
        <CalendarPage onAdjustPlan={navigation.goStudyPlan} />
      )}
      {route.page === "matricula-import" && (
        <MatriculaImportPage onOpenDisciplines={navigation.goDisciplines} />
      )}
    </AppShell>
  );
}
