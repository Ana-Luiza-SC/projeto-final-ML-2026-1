import { useState, type FormEvent } from "react";

type Props = { onHome: () => void; onLogin: () => void };

export function RegisterPage({ onHome, onLogin }: Props) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [accepted, setAccepted] = useState(false);
  const [attempted, setAttempted] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const checks = {
    length: password.length >= 8,
    upper: /[A-Z]/.test(password),
    lower: /[a-z]/.test(password),
    number: /\d/.test(password),
  };
  const nameValid = name.trim().length >= 2;
  const emailValid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
  const passwordValid = Object.values(checks).every(Boolean);
  const confirmationValid =
    confirmation.length > 0 && confirmation === password;
  const valid =
    nameValid && emailValid && passwordValid && confirmationValid && accepted;

  function submit(event: FormEvent) {
    event.preventDefault();
    setAttempted(true);
    setNotice(null);
    if (!valid) return;
    setPassword("");
    setConfirmation("");
    setNotice(
      "O cadastro público ainda não está disponível. Solicite ao responsável pelo ambiente as credenciais de demonstração e use a página de login.",
    );
  }

  return (
    <main className="auth-page register-page">
      <section className="auth-intro" aria-labelledby="register-title">
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
          <p className="eyebrow">Cadastro futuro</p>
          <h1 id="register-title">Prepare seu acesso ao EstudaUnB.</h1>
          <p>
            Este formulário permite conhecer os requisitos, mas não envia nem
            armazena seus dados nesta versão.
          </p>
        </div>
        <div className="message warning">
          <strong>Cadastro público desabilitado</strong>
          <p>
            O MVP usa somente usuários de demonstração configurados pelo
            responsável.
          </p>
        </div>
      </section>
      <section className="auth-form-column">
        <form className="panel auth-card" onSubmit={submit} noValidate>
          <div>
            <p className="eyebrow">Criar conta</p>
            <h2>Preencha os dados para validar o formulário</h2>
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
              Li e aceito os termos de uso e a política de privacidade do
              ambiente acadêmico.
            </span>
          </label>
          {attempted && !accepted && (
            <p className="field-error" id="register-terms-error">
              O aceite é necessário para validar o formulário.
            </p>
          )}
          {notice && (
            <p className="message warning" role="status">
              {notice}
            </p>
          )}
          <button type="submit">Verificar disponibilidade do cadastro</button>
          <p className="auth-privacy-note">
            Nenhuma informação deste formulário será enviada ou salva.
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
              Já possui acesso?{" "}
              <a
                href="/login"
                onClick={(event) => {
                  event.preventDefault();
                  onLogin();
                }}
              >
                Entrar
              </a>
            </span>
          </div>
        </form>
      </section>
    </main>
  );
}
