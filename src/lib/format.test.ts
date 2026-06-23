import { describe, expect, it } from "vitest";
import { formatClock, progressLabel } from "./format";

describe("formatClock", () => {
  it("formats minute-scale timestamps", () => {
    expect(formatClock(83.4)).toBe("01:23");
  });

  it("formats hour-scale timestamps", () => {
    expect(formatClock(3661)).toBe("1:01:01");
  });

  it("guards invalid timestamps", () => {
    expect(formatClock(Number.NaN)).toBe("00:00");
    expect(formatClock(-1)).toBe("00:00");
  });
});

describe("progressLabel", () => {
  it("bounds progress to a percentage", () => {
    expect(progressLabel(0.342)).toBe("34%");
    expect(progressLabel(4)).toBe("100%");
  });
});
