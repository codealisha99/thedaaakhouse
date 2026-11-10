"use client";

import { SignUp } from "@clerk/nextjs";
import { useAppAuth } from "@/components/auth-provider";
import { AuthLayout } from "@/components/auth-layout";
import { LinkButton } from "@/components/ds";

export default function SignUpPage() {
  const auth = useAppAuth();
  if (!auth.clerkEnabled) {
    return (
      <AuthLayout title="Create your account" subtitle="This server uses local accounts. Create one from the login screen.">
        <LinkButton href="/login" variant="primary" size="lg" className="w-full">Go to login</LinkButton>
      </AuthLayout>
    );
  }
  return (
    <AuthLayout title="Create your account" subtitle="Start tracking applications in one place.">
      <SignUp signInUrl="/login" forceRedirectUrl="/applications" />
    </AuthLayout>
  );
}
