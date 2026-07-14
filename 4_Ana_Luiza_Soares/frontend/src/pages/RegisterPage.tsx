import {
  useEffect,
  useRef,
  useState,
  type FormEvent,
} from "react";
import {
  getRegistrationStatus,
  registerAccount,
  type AuthUser,
} from "../api/client";

type Props = {
  onHome: () => void;
  onLogin: () => void;
  onRegistered: (user: AuthUser) => void;
};

type Availability = "loading" | "enabled" | "disabled" | "error";

function BrandLink({ onHome }: { onHome: () => void }) {
  return (
    <a
      className="public-brand"
      href="/"
      onClick={(event) => {
        event.preventDefault();
        onHome();
      }}
    >
      <span className="brand-mark" aria-hidden="true">
        E
      </span>
      <span>
        <strong>EstudaUnB</strong>
        <small>Organização acadêmica</small>
      </span>
    </a>
  );
}

function LoginLink({ onLogin }: { onLogin: () => void }) {
  return (
    <a
      href="/login"
      onClick={(event) => {
        event.preventDefault();
        onLogin();
      }}
    >
      Entrar
    </a>
  );
}

export function RegisterPage({
  onHome,
  onLogin,
  onRegistered,
}: Props) {
  const [availability, setAvailability] =
    useState<Availability>("loading");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [accepted, setAccepted] = useState(false);
  const [attempted, setAttempted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const submittingRef = useRef(false);

  const checks = {
    length: password.length >= 8,
    upper: /[A-Z]/.test(password),
    lower: /[a-z]/.test(password),
    number: /\d/.test(password),
  };
  const nameValid = name.trim().length >= 2;
  const emailValid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());
  const passwordValid = Object.values(checks).every(Boolean);
  const confirmationValid =
    confirmation.length > 0 && confirmation === password;
  const valid =
    nameValid && emailValid && passwordValid && confirmationValid && accepted;

  async function loadStatus() {
    setAvailability("loading");
    setError(null);
    try {
      const status = await getRegistrationStatus();
      setAvailability(status.enabled ? "enabled" : "disabled");
    } catch {
      setAvailability("error");
      setError(
        "Não foi possível verificar se o cadastro está disponível.",
      );
    }
  }

  useEffect(() => {
    void loadStatus();
  }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setAttempted(true);
    setError(null);
    if (!valid || submittingRef.current) return;
    submittingRef.current = true;
    setSubmitting(true);
    try {
      const user = await registerAccount({
        name: name.trim(),
        email: email.trim(),
        password,
        accepted_terms: true,
      });
      setPassword("");
      setConfirmation("");
      onRegistered(user);
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Não foi possível criar a conta. Tente novamente.",
      );
    } finally {
      submittingRef.current = false;
      setSubmitting(false);
    }
  }

  if (availability === "loading") {
    return (
      <main className="auth-loading" aria-live="polite">
        <span className="spinner" aria-hidden="true" />
        <p>Verificando disponibilidade do cadastro...</p>
      </main>
    );
  }

  if (availability === "disabled" || availability === "error") {
    return (
      <main className="auth-page register-page">
        <section className="auth-intro">
          <BrandLink onHome={onHome} />
          <div>
            <p className="eyebrow">Criar conta</p>
            <h1>Cadastro do EstudaUnB</h1>
            <p>
              O acesso a disciplinas, planejamento e calendário é protegido
              por uma conta individual.
            </p>
          </div>
        </section>
        <section className="auth-form-column">
          <div className="panel auth-card">
            <h2>
              {availability === "disabled"
                ? "Cadastro indisponível"
                : "Não foi possível consultar o cadastro"}
            </h2>
            <p className={availability === "error" ? "message error" : "message muted"} role={availability === "error" ? "alert" : "status"}>
              {availability === "disabled"
                ? "A criação de novas contas está desativada neste ambiente."
                : error}
            </p>
            {availability === "error" && (
              <button type="button" onClick={() => void loadStatus()}>
                Tentar novamente
              </button>
            )}
            <div className="auth-links">
              <span>
                Já possui acesso? <LoginLink onLogin={onLogin} />
              </span>
              <a
                href="/"
                onClick={(event) => {
                  event.preventDefault();
                  onHome();
                }}
              >
                Voltar à página inicial
              </a>
            </div>
          </div>
        </section>
      </main>
    );
  }

  return (
    <main className="auth-page register-page">
      <section className="auth-intro" aria-labelledby="register-title">
        <BrandLink onHome={onHome} />
        <div>
          <p className="eyebrow">Criar conta</p>
          <h1 id="register-title">Organize seus estudos no EstudaUnB.</h1>
          <p>
            Crie seu acesso individual para manter disciplinas, avaliações e
            planejamento isolados de outros usuários.
          </p>
        </div>
        <ul className="auth-benefits">
          <li>Dados acadêmicos isolados por usuário</li>
          <li>Senha armazenada somente como hash seguro</li>
          <li>Recomendações com evidências e fallback</li>
        </ul>
      </section>
      <section className="auth-form-column">
        <form
          className="panel auth-card"
          onSubmit={submit}
          noValidate
          aria-busy={submitting}
        >
          <div>
            <p className="eyebrow">Criar conta</p>
            <h2>Informe seus dados de acesso</h2>
          </div>
          <label htmlFor="register-name">Nome</label>
          <input
            id="register-name"
            autoComplete="name"
            maxLength={120}
            value={name}
            aria-invalid={attempted && !nameValid}
            aria-describedby={
              attempted && !nameValid ? "register-name-error" : undefined
            }
            onChange={(event) => setName(event.target.value)}
          />
          {attempted && !nameValid && (
            <p className="field-error" id="register-name-error">
              Informe pelo menos 2 caracteres.
            </p>
          )}
          <label htmlFor="register-email">E-mail</label>
          <input
            id="register-email"
            type="email"
            autoComplete="email"
            maxLength={320}
            value={email}
            aria-invalid={attempted && !emailValid}
            aria-describedby={
              attempted && !emailValid ? "register-email-error" : undefined
            }
            onChange={(event) => setEmail(event.target.value)}
          />
          {attempted && !emailValid && (
            <p className="field-error" id="register-email-error">
              Informe um e-mail válido.
            </p>
          )}
          <label htmlFor="register-password">Senha</label>
          <div className="password-input">
            <input
              id="register-password"
              type={showPassword ? "text" : "password"}
              autoComplete="new-password"
              maxLength={200}
              value={password}
              aria-invalid={attempted && !passwordValid}
              aria-describedby="password-requirements"
              onChange={(event) => setPassword(event.target.value)}
            />
            <button
              className="password-toggle"
              type="button"
              aria-pressed={showPassword}
              aria-controls="register-password register-confirmation"
              onClick={() => setShowPassword((value) => !value)}
            >
              {showPassword ? "Ocultar" : "Mostrar"}
            </button>
          </div>
          <ul
            className="password-requirements"
            id="password-requirements"
            aria-label="Requisitos da senha"
          >
            <li className={checks.length ? "met" : ""}>8 ou mais caracteres</li>
            <li className={checks.upper ? "met" : ""}>Uma letra maiúscula</li>
            <li className={checks.lower ? "met" : ""}>Uma letra minúscula</li>
            <li className={checks.number ? "met" : ""}>Um número</li>
          </ul>
          <label htmlFor="register-confirmation">Confirmar senha</label>
          <input
            id="register-confirmation"
            type={showPassword ? "text" : "password"}
            autoComplete="new-password"
            maxLength={200}
            value={confirmation}
            aria-invalid={attempted && !confirmationValid}
            aria-describedby={
              attempted && !confirmationValid
                ? "register-confirmation-error"
                : undefined
            }
            onChange={(event) => setConfirmation(event.target.value)}
          />
          {attempted && !confirmationValid && (
            <p className="field-error" id="register-confirmation-error">
              As senhas devem ser iguais.
            </p>
          )}
          <label className="terms-row" htmlFor="register-terms">
            <input
              id="register-terms"
              className="content-checkbox"
              type="checkbox"
              checked={accepted}
              aria-invalid={attempted && !accepted}
              aria-describedby={
                attempted && !accepted ? "register-terms-error" : undefined
              }
              onChange={(event) => setAccepted(event.target.checked)}
            />
            <span>
              Li e aceito os termos de uso e a política de privacidade.
            </span>
          </label>
          {attempted && !accepted && (
            <p className="field-error" id="register-terms-error">
              O aceite é necessário para criar a conta.
            </p>
          )}
          {error && (
            <p className="message error" role="alert">
              {error}
            </p>
          )}
          <button type="submit" disabled={submitting}>
            {submitting ? (
              <>
                <span className="spinner auth-spinner" aria-hidden="true" />
                Criando conta...
              </>
            ) : (
              "Criar conta"
            )}
          </button>
          <p className="auth-privacy-note">
            Sua senha é transmitida somente para autenticação e armazenada
            como hash seguro.
          </p>
          <div className="auth-links">
            <a
              href="/"
              onClick={(event) => {
                event.preventDefault();
                onHome();
              }}
            >
              Voltar à página inicial
            </a>
            <span>
              Já possui acesso? <LoginLink onLogin={onLogin} />
            </span>
          </div>
        </form>
      </section>
    </main>
  );
}
