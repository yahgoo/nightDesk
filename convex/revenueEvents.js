import { mutation } from "./_generated/server";
import { v } from "convex/values";

// Record a revenue event (e.g. a S$10 deposit via Dodo Payments, stretch goal).
export const create = mutation({
  args: {
    bookingId: v.optional(v.string()),
    amountSgd: v.number(),
    type: v.string(),
  },
  handler: async (ctx, args) => {
    const createdAt = Date.now();
    return await ctx.db.insert("revenueEvents", { ...args, createdAt });
  },
});
