import { z } from "zod";

export const loginSchema = z.object({
  email: z.string().email(),
  password: z.string().min(1, "Password is required")
});

export const signupSchema = z.object({
  company_name: z.string().min(2),
  company_slug: z
    .string()
    .min(3, "Slug must be at least 3 characters")
    .regex(/^[a-z0-9]+(?:-[a-z0-9]+)*$/, "Use lowercase letters, numbers, and hyphens"),
  first_name: z.string().min(1),
  last_name: z.string().min(1),
  email: z.string().email(),
  password: z.string().min(8, "At least 8 characters")
});

export const forgotSchema = z.object({
  email: z.string().email()
});

export const resetSchema = z.object({
  email: z.string().email(),
  code: z.string().length(6),
  new_password: z.string().min(8)
});

export const otpSchema = z.object({
  email: z.string().email(),
  code: z.string().length(6),
  purpose: z.enum(["LOGIN", "REGISTER", "PASSWORD_RESET", "EMAIL_VERIFY", "PHONE_VERIFY", "MFA"])
});

export const agentSchema = z.object({
  name: z.string().min(2),
  description: z.string().optional(),
  system_prompt_template: z.string().min(10),
  temperature: z.coerce.number().min(0).max(2)
});

export const domainSchema = z.object({
  hostname: z.string().min(3),
  verification_method: z.enum(["TXT", "CNAME"]),
  is_primary: z.boolean()
});

export const profileSchema = z.object({
  first_name: z.string().min(1),
  last_name: z.string().min(1),
  email: z.string().email()
});

export const companySchema = z.object({
  name: z.string().min(2),
  brand_color: z.string().optional(),
  logo_url: z.string().url().optional().or(z.literal(""))
});

export const webhookSchema = z.object({
  url: z.string().url("Enter a valid HTTPS URL"),
  event_types: z.array(z.string()).min(1, "Select at least one event")
});
