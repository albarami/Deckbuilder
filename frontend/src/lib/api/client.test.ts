/**
 * Tests for the API fetch wrapper.
 *
 * Uses vi.fn() to mock global fetch — no real HTTP calls.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { get, post, postFormData } from "./client";
import { APIError } from "@/lib/types/api";

// Mock global fetch
const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

beforeEach(() => {
  mockFetch.mockReset();
});

describe("API Client", () => {
  describe("get()", () => {
    it("returns parsed JSON on success", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ status: "ok" }),
      });

      const result = await get("/api/health");
      expect(result).toEqual({ status: "ok" });
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/health"),
        expect.objectContaining({ method: "GET" }),
      );
    });

    it("throws APIError on 404", async () => {
      const mockResponse = {
        ok: false,
        status: 404,
        statusText: "Not Found",
        json: () =>
          Promise.resolve({
            detail: {
              error: {
                code: "SESSION_NOT_FOUND",
                message: "Session not found",
              },
            },
          }),
      };

      mockFetch.mockResolvedValueOnce(mockResponse);
      await expect(get("/api/pipeline/bad-id/status")).rejects.toThrow(
        APIError,
      );

      // Verify error details with a fresh mock
      mockFetch.mockResolvedValueOnce(mockResponse);
      try {
        await get("/api/pipeline/bad-id/status");
      } catch (err) {
        expect(err).toBeInstanceOf(APIError);
        const apiErr = err as APIError;
        expect(apiErr.status).toBe(404);
        expect(apiErr.code).toBe("SESSION_NOT_FOUND");
      }
    });

    it("handles non-JSON error responses", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        statusText: "Internal Server Error",
        json: () => Promise.reject(new Error("Not JSON")),
      });

      await expect(get("/api/health")).rejects.toThrow(APIError);
    });
  });

  describe("post()", () => {
    it("sends JSON body and returns parsed response", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 201,
        json: () =>
          Promise.resolve({
            session_id: "test-123",
            status: "running",
          }),
      });

      const result = await post("/api/pipeline/start", {
        text_input: "Test",
        language: "en",
      });

      expect(result).toEqual({
        session_id: "test-123",
        status: "running",
      });

      // Check Content-Type header
      const [, options] = mockFetch.mock.calls[0];
      expect(options.headers["Content-Type"]).toBe("application/json");
    });

    it("throws APIError on 422 validation error", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 422,
        statusText: "Unprocessable Entity",
        json: () =>
          Promise.resolve({
            detail: {
              error: {
                code: "INVALID_INPUT",
                message: "Input required",
              },
            },
          }),
      });

      await expect(
        post("/api/pipeline/start", {}),
      ).rejects.toThrow(APIError);
    });
  });

  describe("postFormData()", () => {
    it("sends FormData without Content-Type header", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () =>
          Promise.resolve({
            uploads: [{ upload_id: "u1", filename: "test.txt" }],
          }),
      });

      const formData = new FormData();
      formData.append("files", new Blob(["test"]), "test.txt");

      await postFormData("/api/upload", formData);

      // Should NOT set Content-Type (let browser handle multipart boundary)
      const [, options] = mockFetch.mock.calls[0];
      expect(options.headers).not.toHaveProperty("Content-Type");
    });
  });
});
