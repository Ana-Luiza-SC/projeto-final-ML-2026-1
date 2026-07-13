import type { AuthUser } from "../api/client";

type Props = {
  user: AuthUser | null;
  onLogin: () => void;
  onRegister: () => void;
  onDashboard: () => void;
};

const features = [
  {
    title: "Importação acadêmica",
    text: "Importe o comprovante de matrícula e revise os dados antes de confirmar.",
  },
  {
    title: "Disciplinas organizadas",
    text: "Reúna horários, ementa, avaliações, notas, conteúdos e frequência em um só lugar.",
  },
  {
    title: "Conteúdos e avaliações",
    text: "Extraia uma proposta do plano de ensino e confirme a estrutura que será usada pelo produto.",
  },
  {
    title: "Recomendações assistidas",
    text: "Receba ações de estudo específicas, ligadas a evidências e estratégias fundamentadas.",
  },
  {
    title: "Planejamento semanal",
    text: "Distribua minutos disponíveis sem ultrapassar prazos confirmados das avaliações.",
  },
  {
    title: "Calendário acadêmico",
    text: "Funcionalidade futura planejada para reunir prazos acadêmicos confirmados.",
  },
];

export function PublicLandingPage({
  user,
  onLogin,
  onRegister,
  onDashboard,
}: Props) {
  return (
    <div className="public-site">
      <header className="public-header">
        <a
          className="public-brand"
          href="/"
          aria-label="EstudaUnB — página inicial"
        >
          <span className="brand-mark" aria-hidden="true">
            E
          </span>
          <span>
            <strong>EstudaUnB</strong>
            <small>Organização acadêmica com evidências</small>
          </span>
        </a>
        <nav aria-label="Navegação pública">
          <a href="#recursos">Recursos</a>
          <a href="#como-funciona">Como funciona</a>
          {user ? (
            <a
              className="button public-nav-action"
              href="/app"
              onClick={(event) => {
                event.preventDefault();
                onDashboard();
              }}
            >
              Ir para o painel
            </a>
          ) : (
            <a
              className="button public-nav-action"
              href="/login"
              onClick={(event) => {
                event.preventDefault();
                onLogin();
              }}
            >
              Entrar
            </a>
          )}
        </nav>
      </header>

      <main>
        <section className="public-hero">
          <div className="public-hero-copy">
            <p className="eyebrow">
              Projeto acadêmico · Universidade de Brasília
            </p>
            <h1>
              Transforme dados acadêmicos dispersos em prioridades de estudo
              claras.
            </h1>
            <p className="public-lead">
              O EstudaUnB ajuda estudantes a organizar disciplinas, confirmar
              avaliações e conteúdos e planejar a semana sem delegar cálculos
              acadêmicos à IA.
            </p>
            <div className="public-actions">
              <a
                className="button"
                href={user ? "/app" : "/login"}
                onClick={(event) => {
                  event.preventDefault();
                  user ? onDashboard() : onLogin();
                }}
              >
                {user ? "Ir para o painel" : "Entrar"}
              </a>
              <a
                className="button secondary-button"
                href="/register"
                onClick={(event) => {
                  event.preventDefault();
                  onRegister();
                }}
              >
                Criar conta
              </a>
            </div>
            <p className="public-note">
              O cadastro público ainda não está disponível. O ambiente de
              demonstração usa acesso fornecido pelo responsável.
            </p>
          </div>
          <aside className="public-hero-card" aria-label="Resumo do produto">
            <span className="status-badge badge-success">Fluxo auditável</span>
            <h2>
              Você confirma os dados. O sistema calcula. O agente explica.
            </h2>
            <ul className="public-check-list">
              <li>Cálculos de notas e frequência determinísticos</li>
              <li>Prioridades ligadas a avaliações e conteúdos reais</li>
              <li>Fallback identificado quando o LLM não responde</li>
            </ul>
          </aside>
        </section>

        <section
          className="public-section"
          id="recursos"
          aria-labelledby="features-title"
        >
          <div className="public-section-heading">
            <p className="eyebrow">Recursos principais</p>
            <h2 id="features-title">Do cadastro ao plano de estudos</h2>
            <p>
              Um núcleo pequeno para manter dados acadêmicos revisáveis e
              transformar contexto confirmado em próximas ações.
            </p>
          </div>
          <div className="public-feature-grid">
            {features.map((feature, index) => (
              <article key={feature.title} className="public-feature">
                <span aria-hidden="true">
                  {String(index + 1).padStart(2, "0")}
                </span>
                <h3>{feature.title}</h3>
                <p>{feature.text}</p>
                {feature.title === "Calendário acadêmico" && (
                  <small>Planejado para uma próxima iteração</small>
                )}
              </article>
            ))}
          </div>
        </section>

        <section className="public-trust" aria-labelledby="trust-title">
          <div>
            <p className="eyebrow">Confiabilidade</p>
            <h2 id="trust-title">Assistência sem esconder incertezas</h2>
          </div>
          <div className="public-trust-grid">
            <article>
              <strong>Confirmação humana</strong>
              <p>
                Dados extraídos aparecem em uma prévia editável antes de serem
                persistidos.
              </p>
            </article>
            <article>
              <strong>Evidências visíveis</strong>
              <p>
                Recomendações citam avaliações, datas, conteúdos e estados que
                sustentaram a prioridade.
              </p>
            </article>
            <article>
              <strong>Degradação graciosa</strong>
              <p>
                Sem LLM, regras locais continuam produzindo respostas
                identificadas e auditáveis.
              </p>
            </article>
          </div>
        </section>

        <section
          className="public-section public-flow"
          id="como-funciona"
          aria-labelledby="flow-title"
        >
          <div className="public-section-heading">
            <p className="eyebrow">Como funciona</p>
            <h2 id="flow-title">Três passos para organizar a próxima semana</h2>
          </div>
          <ol>
            <li>
              <span>1</span>
              <div>
                <strong>Importe ou cadastre seus dados</strong>
                <p>
                  Comece pelo comprovante de matrícula ou pelo cadastro manual.
                </p>
              </div>
            </li>
            <li>
              <span>2</span>
              <div>
                <strong>Confirme avaliações e conteúdos</strong>
                <p>
                  Revise datas, pesos, hierarquia e associações antes de usar os
                  dados.
                </p>
              </div>
            </li>
            <li>
              <span>3</span>
              <div>
                <strong>Receba prioridades e plano de estudos</strong>
                <p>
                  O backend respeita prazos e disponibilidade; o agente explica
                  as ações.
                </p>
              </div>
            </li>
          </ol>
        </section>
      </main>

      <footer className="public-footer">
        <span>EstudaUnB · Projeto acadêmico da Universidade de Brasília</span>
        <span>MVP auditável para organização dos estudos</span>
      </footer>
    </div>
  );
}
