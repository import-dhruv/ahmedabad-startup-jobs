import { Suspense } from "react";
import type { Metadata } from "next";

import { LoginForm } from "@/components/login-form";

export const metadata: Metadata = {
  title: "Sign in",
  description: "Sign in to track saved Ahmedabad startup jobs, alerts and applications.",
  robots: { index: false, follow: true },
};

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginForm />
    </Suspense>
  );
}
