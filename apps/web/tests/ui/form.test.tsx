import { axe } from "jest-axe";
import { useState } from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

describe("Button pending state", () => {
  it("blocks duplicate submits while a request is in flight", async () => {
    const user = userEvent.setup();
    const handleSubmit = vi.fn();

    function SaveButton() {
      const [pending, setPending] = useState(false);
      return (
        <Button
          pending={pending}
          onClick={() => {
            handleSubmit();
            setPending(true);
            // In a real screen an async completion clears this; the test
            // keeps it pending to prove double-fire prevention.
          }}
        >
          Save research
        </Button>
      );
    }

    render(<SaveButton />);
    const button = screen.getByRole("button", { name: /Save research/ });
    await user.click(button);
    await user.click(button); // ignored: aria-busy disables the control
    await user.dblClick(button);
    expect(handleSubmit).toHaveBeenCalledTimes(1);
    expect(button).toHaveAttribute("aria-busy", "true");
    expect(button).toBeDisabled();
    expect(await axe(document.body, {
      // Landmark structure is a page-level concern (NI-008 layout shells);
      // component tests judge the component itself.
      rules: { region: { enabled: false } },
    })).toHaveNoViolations();
  });
});

describe("Input error state", () => {
  it("keeps the typed value, announces the error and stays labeled", async () => {
    const user = userEvent.setup();
    render(
      <div>
        <Label htmlFor="title">Document title</Label>
        <Input id="title" error="Title is required" placeholder="Untitled" />
      </div>,
    );

    const input = screen.getByLabelText("Document title");
    await user.type(input, "NEAR fees");
    expect(input).toHaveValue("NEAR fees");

    const message = screen.getByRole("alert");
    expect(message).toHaveTextContent("Title is required");
    expect(input).toBeInvalid();
    expect(input).toHaveAccessibleDescription("Title is required");
    expect(await axe(document.body, {
      // Landmark structure is a page-level concern (NI-008 layout shells);
      // component tests judge the component itself.
      rules: { region: { enabled: false } },
    })).toHaveNoViolations();
  });
});

describe("Touch targets", () => {
  it("render controls at the 44px minimum height", () => {
    render(
      <div>
        <Button>Primary</Button>
        <Button variant="secondary">Secondary</Button>
        <Button variant="quiet">Quiet</Button>
        <Button variant="destructive">Delete</Button>
        <Input />
      </div>,
    );
    for (const name of ["Primary", "Secondary", "Quiet", "Delete"]) {
      const button = screen.getByRole("button", { name });
      expect(button).toHaveClass("h-11"); // 44px token-based height
    }
    expect(screen.getByRole("textbox")).toHaveClass("h-11");
  });
});
