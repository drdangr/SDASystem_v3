/**
 * LLM client for calling backend /api/llm/generate
 * @param {Object} params
 * @param {'summary'|'bullets'|'domains'|'events'} params.task
 * @param {string} params.text
 * @param {string} [params.title]
 * @param {Object} [params.settings] - { model, temperature, top_p, top_k, max_tokens }
 */
export async function llmGenerate({ task, text, title = '', settings = {} }) {
    const payload = {
        task,
        text,
        title,
    };

    const { model, temperature, top_p, top_k, max_tokens } = settings;
    if (model) payload.model = model;
    if (temperature !== undefined) payload.temperature = temperature;
    if (top_p !== undefined) payload.top_p = top_p;
    if (top_k !== undefined) payload.top_k = top_k;
    if (max_tokens !== undefined) payload.max_tokens = max_tokens;

    const resp = await fetch('/api/llm/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });

    if (!resp.ok) {
        const textResp = await resp.text();
        throw new Error(`LLM call failed: ${resp.status} ${textResp}`);
    }

    return resp.json();
}

