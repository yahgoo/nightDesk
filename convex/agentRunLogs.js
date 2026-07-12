import { mutation } from "./_generated/server";
import { v } from "convex/values";

// Persist one structured agent run-log event emitted by logging_utils.
export const create = mutation({
  args: {
    runId: v.string(),
    conversationId: v.string(),
    agent: v.string(),
    intent: v.optional(v.string()),
    eventType: v.string(),
    detail: v.any(),
    level: v.string(),
    ts: v.number(),
    tsIso: v.string(),
  },
  handler: async (ctx, args) => {
    return await ctx.db.insert("agentRunLogs", args);
  },
});
