import { useEffect, useMemo, useState } from "react";
import { HomePage } from "./pages/HomePage";
import { DisciplinesPage } from "./pages/DisciplinesPage";
import { DisciplineDetailPage } from "./pages/DisciplineDetailPage";
import { StudyPlanPage } from "./pages/StudyPlanPage";

type Route = { page: "home" } | { page: "disciplines" } | { page: "discipline"; id: string } | { page: "study-plan" };

function parseHash(): Route {
  const hash = window.location.hash.replace(/^#/, "");
  if (hash.startsWith("/disciplines/")) {
    const id = hash.split("/")[2];
    if (id) return { page: "discipline", id };
  }
  if (hash === "/disciplines") return { page: "disciplines" };
  if (hash === "/study-plan") return { page: "study-plan" };
  return { page: "home" };
}

function setHash(route: Route) {
  if (route.page === "home") window.location.hash = "/";
  if (route.page === "disciplines") window.location.hash = "/disciplines";
  if (route.page === "discipline") window.location.hash = `/disciplines/${route.id}`;
  if (route.page === "study-plan") window.location.hash = "/study-plan";
}

export default function App() {
  const [route, setRoute] = useState<Route>(() => parseHash());

  useEffect(() => {
    const onHashChange = () => setRoute(parseHash());
    window.addEventListener("hashchange", onHashChange);
    if (!window.location.hash) setHash({ page: "home" });
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  const navigation = useMemo(
    () => ({
      goHome: () => setHash({ page: "home" }),
      goDisciplines: () => setHash({ page: "disciplines" }),
      goDiscipline: (id: string) => setHash({ page: "discipline", id }),
      goStudyPlan: () => setHash({ page: "study-plan" }),
    }),
    [],
  );

  return (
    <div className="app-shell">
      <header className="topbar">
        <button className="brand-button" onClick={navigation.goHome}>EstudaUnB</button>
        <nav>
          <button onClick={navigation.goDisciplines}>Disciplinas</button>
          <button onClick={navigation.goStudyPlan}>Planejamento</button>
          <a href="http://localhost:8000/docs" target="_blank" rel="noreferrer">Swagger</a>
        </nav>
      </header>
      <main>
        {route.page === "home" && <HomePage onOpenDisciplines={navigation.goDisciplines} />}
        {route.page === "disciplines" && <DisciplinesPage onOpenDiscipline={navigation.goDiscipline} />}
        {route.page === "discipline" && (
          <DisciplineDetailPage disciplineId={route.id} onBack={navigation.goDisciplines} />
        )}
        {route.page === "study-plan" && <StudyPlanPage />}
      </main>
    </div>
  );
}
