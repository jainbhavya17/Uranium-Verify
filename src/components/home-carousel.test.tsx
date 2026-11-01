import { render, screen, fireEvent, cleanup, act } from "@testing-library/react";
import { afterEach, beforeEach, describe, it, expect, vi } from "vitest";
import { HomeCarousel } from "./home-carousel";
vi.mock("./link", () => ({
  Link: ({ to, children, ...props }: { to: string; children: React.ReactNode }) => (
    <a href={to} {...props}>
      {children}
    </a>
  ),
}));
beforeEach(() => vi.useFakeTimers());
afterEach(() => {
  cleanup();
  vi.useRealTimers();
});
describe("homepage journey carousel", () => {
  it("retains the campus artwork and lets a user navigate the cards", () => {
    render(<HomeCarousel campus={<div>University artwork</div>} />);
    expect(screen.getByText("University artwork")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Next slide" }));
    expect(
      screen.getByRole("heading", { name: "The right documents. Clearly defined." }),
    ).toBeVisible();
    expect(screen.getByText("University artwork")).not.toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Previous slide" }));
    expect(screen.getByText("University artwork")).toBeVisible();
  });
  it("pauses automatic rotation when requested", () => {
    render(<HomeCarousel campus={<div>University artwork</div>} />);
    fireEvent.click(screen.getByRole("button", { name: "Pause slides" }));
    act(() => vi.advanceTimersByTime(21000));
    expect(screen.getByText("University artwork")).toBeVisible();
    expect(screen.getByRole("button", { name: "Play slides" })).toBeVisible();
  });
  it("does not advance while keyboard focus is within the carousel", () => {
    render(<HomeCarousel campus={<div>University artwork</div>} />);
    fireEvent.focus(screen.getByRole("button", { name: "Next slide" }));
    act(() => vi.advanceTimersByTime(14000));
    expect(screen.getByText("University artwork")).toBeVisible();
  });
});
