import { useState, type FormEvent } from "react";
import { login, type AuthUser } from "../api/client";

type Props = {
  onLogin: (user: AuthUser) => void;
  onHome: () => void;
  onRegister: () => void;
};

export function LoginPage({ onLogin, onHome, onRegister }: Props) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [attempted, setAttempted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const emailValid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
  const passwordValid = password.length >= 8;

  async function submit(event: FormEvent) {
    event.preventDefault();
    setAttempted(true);
    setError(null);
    if (!emailValid || !passwordValid) return;
    setLoading(true);
    try {
      onLogin(await login(email, password));
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Não foi possível entrar. Tente novamente.",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="auth-page">
      <section className="auth-intro" aria-labelledby="login-title">
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
        <div>
          <p className="eyebrow">Acesso ao ambiente</p>
          <h1 id="login-title">Continue sua organização acadêmica.</h1>
          <p>
            Entre para acessar disciplinas, avaliações, conteúdos, recomendações
            e planejamento semanal.
          </p>
        </div>
        <ul className="auth-benefits">
          <li>Dados isolados por usuário</li>
          <li>Cálculos acadêmicos determinísticos</li>
          <li>Recomendações com evidências e fallback</li>
        </ul>
      </section>
      <section className="auth-form-column">
        <form
          className="panel auth-card"
          onSubmit={submit}
          noValidate
          aria-busy={loading}
        >
          <div>
            <p className="eyebrow">Entrar</p>
            <h2>Entre com sua conta</h2>
            <p className="muted">
              Use o e-mail e a senha cadastrados neste ambiente.
            </p>
          </div>
          <label htmlFor="login-email">E-mail</label>
          <input
            id="login-email"
            type="email"
            required
            autoComplete="username"
            value={email}
            aria-invalid={attempted && !emailValid}
            aria-describedby={
              attempted && !emailValid ? "login-email-error" : undefined
            }
            onChange={(event) => setEmail(event.target.value)}
          />
          {attempted && !emailValid && (
            <p className="field-error" id="login-email-error">
              Informe um e-mail válido.
            </p>
          )}
          <label htmlFor="login-password">Senha</label>
          <div className="password-input">
            <input
              id="login-password"
              type={showPassword ? "text" : "password"}
              required
              minLength={8}
              autoComplete="current-password"
              value={password}
              aria-invalid={attempted && !passwordValid}
              aria-describedby={
                attempted && !passwordValid ? "login-password-error" : undefined
              }
              onChange={(event) => setPassword(event.target.value)}
            />
            <button
              className="password-toggle"
              type="button"
              aria-pressed={showPassword}
              aria-controls="login-password"
              onClick={() => setShowPassword((value) => !value)}
            >
              {showPassword ? "Ocultar" : "Mostrar"}
            </button>
          </div>
          {attempted && !passwordValid && (
            <p className="field-error" id="login-password-error">
              A senha deve ter pelo menos 8 caracteres.
            </p>
          )}
          {error && (
            <p className="message error" role="alert">
              {error}
            </p>
          )}
          <button type="submit" disabled={loading}>
            {loading ? (
              <>
                <span className="spinner auth-spinner" aria-hidden="true" />
                Entrando...
              </>
            ) : (
              "Entrar"
            )}
          </button>
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
              Não possui acesso?{" "}
              <a
                href="/register"
                onClick={(event) => {
                  event.preventDefault();
                  onRegister();
                }}
              >
                Criar conta
              </a>
            </span>
          </div>
        </form>
      </section>
    </main>
  );
}
