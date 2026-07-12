import { defineSchema, defineTable } from "convex/server";
import { v } from "convex/values";

// NightDesk Convex schema. Three tables back the whole product:
//  - bookings:       every booking the specialist creates/cancels/reschedules
//  - revenueEvents:  deposit/full-payment events tied to a booking
//  - agentRunLogs:   structured observability for every agent decision + tool call
export default defineSchema({
  bookings: defineTable({
    businessId: v.optional(v.string()),
    telegramUserId: v.string(),
    customerName: v.optional(v.string()),
    service: v.optional(v.string()),
    slotTime: v.optional(v.string()),
    urgency: v.string(),
    status: v.string(),
    source: v.string(),
    createdAt: v.number(),
  }),
  revenueEvents: defineTable({
    bookingId: v.optional(v.string()),
    amountSgd: v.number(),
    type: v.string(),
    createdAt: v.number(),
  }),
  agentRunLogs: defineTable({
    runId: v.string(),
    conversationId: v.string(),
    agent: v.string(),
    intent: v.optional(v.string()),
    eventType: v.string(),
    detail: v.any(),
    level: v.string(),
    ts: v.number(),
    tsIso: v.string(),
  }),
});
