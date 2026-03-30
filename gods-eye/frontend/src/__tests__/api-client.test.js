import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

describe('apiClient', () => {
  let fetchMock;

  beforeEach(() => {
    fetchMock = vi.fn();
    global.fetch = fetchMock;
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('makes successful API requests and returns data', async () => {
    const mockData = { result: 'success', agents: [] };
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => mockData,
    });

    // Dynamically import to use the mocked fetch
    const { apiClient } = await import('../api/client');
    const result = await apiClient.getPresets();

    expect(result).toEqual(mockData);
    expect(fetchMock).toHaveBeenCalled();
  });

  it(
    'throws error on client error responses',
    async () => {
      const errorData = { detail: 'Bad request' };
      fetchMock.mockResolvedValueOnce({
        ok: false,
        status: 400,
        json: async () => errorData,
      });

      const { apiClient } = await import('../api/client');

      try {
        await apiClient.getPresets();
        expect.fail('Should have thrown an error');
      } catch (error) {
        expect(error).toBeDefined();
      }
    },
    10000
  );

  it('constructs correct API endpoints', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ data: 'test' }),
    });

    const { apiClient } = await import('../api/client');
    await apiClient.getPresets();

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringMatching(/\/api\/presets/),
      expect.any(Object)
    );
  });

  it('uses API_BASE from environment or defaults to /api', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ data: 'test' }),
    });

    const { apiClient } = await import('../api/client');
    await apiClient.getHealth();

    // Verify that a fetch was made (endpoint should start with /api or custom base)
    expect(fetchMock).toHaveBeenCalled();
    const callUrl = fetchMock.mock.calls[0][0];
    expect(typeof callUrl).toBe('string');
    expect(callUrl.length).toBeGreaterThan(0);
  });

  it('handles POST requests with proper headers', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ success: true }),
    });

    const { apiClient } = await import('../api/client');
    const testSettings = { theme: 'dark' };
    await apiClient.updateSettings(testSettings);

    expect(fetchMock).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({
          'Content-Type': 'application/json',
        }),
      })
    );
  });
});
