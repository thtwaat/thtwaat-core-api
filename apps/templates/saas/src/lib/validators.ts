import { z } from "zod";

export const loginSchema = z.object({
  email: z.string().email(),
  password: z.string().min(1, "Password is required")
});

export const signupSchema = z.object({
  company_name: z.string().trim().min(2, "Company name is required"),
  first_name: z.string().optional(),
  last_name: z.string().optional(),
  email: z.string().email("Enter a valid email"),
  password: z.string().min(8, "At least 8 characters")
});

export const forgotSchema = z.object({
  email: z.string().email()
});

export const resetSchema = z.object({
  token: z.string().min(20, "Invalid reset link"),
  new_password: z.string().min(8)
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
