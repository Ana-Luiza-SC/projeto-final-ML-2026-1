import { getApiBaseUrl } from "../api/client";
import { ApiStatus } from "../components/ApiStatus";

type Props = {
  onOpenDisciplines: () => void;
  onOpenMatriculaImport?: () => void;
};

export function HomePage({ onOpenDisciplines, onOpenMatriculaImport }: Props) {
  const apiBaseUrl = getApiBaseUrl();

  return (
    <div className="page narrow-page">
      <section className="hero">
        <p className="eyebrow">Produto web mínimo</p>
        <h1>EstudaUnB</h1>
        <p>Organize disciplinas, avaliações, faltas e simulações acadêmicas por menção e frequência.</p>
        <ApiStatus />
        <div className="hero-actions">
          <button type="button" onClick={onOpenDisciplines}>Ir para disciplinas</button>
          {onOpenMatriculaImport && <button type="button" onClick={onOpenMatriculaImport}>Importar comprovante</button>}
          <a href={`${apiBaseUrl}/docs`} target="_blank" rel="noreferrer">Swagger</a>
          <a href={`${apiBaseUrl}/redoc`} target="_blank" rel="noreferrer">ReDoc</a>
        </div>
      </section>
    </div>
  );
}
