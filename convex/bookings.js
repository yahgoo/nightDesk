import { mutation } from "./_generated/server";
import { v } from "convex/values";

// Insert a new booking row and return its id.
export const create = mutation({
  args: {
    businessId: v.optional(v.string()),
    telegramUserId: v.string(),
    customerName: v.optional(v.string()),
    service: v.optional(v.string()),
    slotTime: v.optional(v.string()),
    urgency: v.string(),
    status: v.string(),
    source: v.string(),
  },
  handler: async (ctx, args) => {
    const createdAt = Date.now();
    return await ctx.db.insert("bookings", { ...args, createdAt });
  },
});

// Patch an existing booking (status changes, reschedules, cancellations).
export const update = mutation({
  args: { id: v.id("bookings"), patch: v.any() },
  handler: async (ctx, { id, patch }) => {
    await ctx.db.patch(id, patch);
  },
});

// Read bookings for a given Telegram user (used by the dashboard / FAQs).
export const byUser = mutation({
  args: { telegramUserId: v.string() },
  handler: async (ctx, { telegramUserId }) => {
    return await ctx.db
      .query("bookings")
      .filter((q) => q.eq(q.field("telegramUserId"), telegramUserId))
      .collect();
  },
});
