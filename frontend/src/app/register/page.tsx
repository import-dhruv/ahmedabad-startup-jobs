import type { Metadata } from "next";

import { RegisterForm } from "@/components/register-form";

export const metadata: Metadata = {
  title: "Create an account",
  description: "Create a candidate profile to get matched with Ahmedabad startup roles.",
  robots: { index: false, follow: true },
};

export default function RegisterPage() {
  return <RegisterForm />;
}
