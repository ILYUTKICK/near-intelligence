import { axe } from "jest-axe";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

describe("Dialog primitive", () => {
  it("opens from keyboard, closes on Escape and returns focus to the trigger", async () => {
    const user = userEvent.setup();
    render(
      <Dialog>
        <DialogTrigger>Open source details</DialogTrigger>
        <DialogContent>
          <DialogTitle>Source details</DialogTitle>
          <DialogDescription>Definition, dataset and retrieval timestamps.</DialogDescription>
        </DialogContent>
      </Dialog>,
    );

    await user.tab();
    const trigger = screen.getByRole("button", { name: "Open source details" });
    expect(trigger).toHaveFocus();

    await user.keyboard("{Enter}");
    const dialog = await screen.findByRole("dialog", { name: "Source details" });
    expect(dialog).toBeInTheDocument();

    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });

  it("has no axe violations while open", async () => {
    const user = userEvent.setup();
    render(
      <Dialog>
        <DialogTrigger>Open</DialogTrigger>
        <DialogContent>
          <DialogTitle>Confirm action</DialogTitle>
          <DialogDescription>Explain the consequence before confirming.</DialogDescription>
          <button type="button">Confirm</button>
        </DialogContent>
      </Dialog>,
    );
    await user.click(screen.getByRole("button", { name: "Open" }));
    const dialog = await screen.findByRole("dialog");
    expect(dialog).toBeInTheDocument();
    expect(await axe(document.body, {
      // Landmark structure is a page-level concern (NI-008 layout shells);
      // component tests judge the component itself.
      rules: { region: { enabled: false } },
    })).toHaveNoViolations();
  });
});
