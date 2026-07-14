import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  getRegistrationStatus,
  registerAccount,
} from "../api/client";
import { RegisterPage } from "./RegisterPage";

vi.mock("../api/client", () => ({
  getRegistrationStatus: vi.fn(),
  registerAccount: vi.fn(),
}));

const mockedStatus = vi.mocked(getRegistrationStatus);
const mockedRegister = vi.mocked(registerAccount);

function renderPage(onRegistered = vi.fn()) {
  render(
    <RegisterPage
      onHome={vi.fn()}
      onLogin={vi.fn()}
      onRegistered={onRegistered}
    />,
  );
  return { onRegistered };
}

async function fillValidForm() {
  fireEvent.change(await screen.findByLabelText("Nome"), {
    target: { value: "Lulu" },
  });
  fireEvent.change(screen.getByLabelText("E-mail"), {
    target: { value: "lulu@email.com" },
  });
  fireEvent.change(screen.getByLabelText("Senha"), {
    target: { value: "Lulu123456" },
  });
  fireEvent.change(screen.getByLabelText("Confirmar senha"), {
    target: { value: "Lulu123456" },
  });
  fireEvent.click(
    screen.getByLabelText(/Li e aceito os termos de uso/i),
  );
}

describe("RegisterPage", () => {
  beforeEach(() => {
    mockedStatus.mockReset();
    mockedRegister.mockReset();
  });

  it("renders a loading state before the backend status resolves", () => {
    mockedStatus.mockReturnValue(new Promise(() => undefined));

    renderPage();

    expect(
      screen.getByText("Verificando disponibilidade do cadastro..."),
    ).toBeInTheDocument();
    expect(screen.queryByLabelText("Senha")).not.toBeInTheDocument();
  });

  it("renders the active form when registration is enabled", async () => {
    mockedStatus.mockResolvedValue({ enabled: true });

    renderPage();

    expect(await screen.findByLabelText("Nome")).toBeInTheDocument();
    expect(screen.getByLabelText("Senha")).toHaveAttribute(
      "autocomplete",
      "new-password",
    );
    expect(
      screen.getByRole("button", { name: "Criar conta" }),
    ).toBeEnabled();
  });

  it("does not render the password form when registration is disabled", async () => {
    mockedStatus.mockResolvedValue({ enabled: false });

    renderPage();

    expect(
      await screen.findByRole("heading", { name: "Cadastro indisponível" }),
    ).toBeInTheDocument();
    expect(screen.queryByLabelText("Senha")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Entrar" })).toBeInTheDocument();
  });

  it("authenticates through the existing app callback after registration", async () => {
    mockedStatus.mockResolvedValue({ enabled: true });
    mockedRegister.mockResolvedValue({
      id: "new-user",
      email: "lulu@email.com",
      display_name: "Lulu",
    });
    const { onRegistered } = renderPage();
    await fillValidForm();

    fireEvent.click(screen.getByRole("button", { name: "Criar conta" }));

    await waitFor(() =>
      expect(mockedRegister).toHaveBeenCalledWith({
        name: "Lulu",
        email: "lulu@email.com",
        password: "Lulu123456",
        accepted_terms: true,
      }),
    );
    expect(onRegistered).toHaveBeenCalledWith({
      id: "new-user",
      email: "lulu@email.com",
      display_name: "Lulu",
    });
  });

  it("shows a safe duplicate-email error", async () => {
    mockedStatus.mockResolvedValue({ enabled: true });
    mockedRegister.mockRejectedValue(
      new Error("Já existe uma conta com este e-mail."),
    );
    renderPage();
    await fillValidForm();

    fireEvent.click(screen.getByRole("button", { name: "Criar conta" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Já existe uma conta com este e-mail.",
    );
  });

  it("shows a retry state when status lookup fails", async () => {
    mockedStatus.mockRejectedValue(new Error("network"));

    renderPage();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Não foi possível verificar se o cadastro está disponível.",
    );
    expect(screen.queryByLabelText("Senha")).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Tentar novamente" }),
    ).toBeInTheDocument();
  });

  it("prevents duplicate submissions while the first request is pending", async () => {
    mockedStatus.mockResolvedValue({ enabled: true });
    mockedRegister.mockReturnValue(new Promise(() => undefined));
    renderPage();
    await fillValidForm();
    const submit = screen.getByRole("button", { name: "Criar conta" });

    fireEvent.click(submit);
    fireEvent.submit(submit.closest("form") as HTMLFormElement);

    expect(mockedRegister).toHaveBeenCalledTimes(1);
    expect(
      screen.getByRole("button", { name: /Criando conta/ }),
    ).toBeDisabled();
  });
});
