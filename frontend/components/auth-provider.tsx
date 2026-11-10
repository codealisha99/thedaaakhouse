"use client";

import { ClerkProvider, useAuth, useClerk, useUser } from "@clerk/nextjs";
import { createContext, useContext } from "react";
import { setAuthTokenProvider } from "@/lib/api";

type AuthState = {
  clerkEnabled: boolean;
  loaded: boolean;
  signedIn: boolean;
  displayName: string | null;
  signOut: () => Promise<void>;
};

const localAuth: AuthState = {
  clerkEnabled: false,
  loaded: true,
  signedIn: false,
  displayName: null,
  signOut: async () => {},
};

const AuthContext = createContext<AuthState>(localAuth);
export const useAppAuth = () => useContext(AuthContext);

function ClerkSession({ children }: { children: React.ReactNode }) {
  const { isLoaded, isSignedIn, getToken } = useAuth();
  const { signOut } = useClerk();
  const { user } = useUser();
  // Set this during render so descendant route effects can make authenticated
  // API calls as soon as Clerk reports a loaded session.
  setAuthTokenProvider(getToken);
  const displayName = user?.fullName || user?.primaryEmailAddress?.emailAddress || null;
  const state: AuthState = {
    clerkEnabled: true,
    loaded: isLoaded,
    signedIn: Boolean(isSignedIn),
    displayName,
    signOut: async () => { await signOut(); },
  };
  return <AuthContext.Provider value={state}>{children}</AuthContext.Provider>;
}

export default function AuthProvider({ children }: { children: React.ReactNode }) {
  const publishableKey = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;
  if (!publishableKey) return <AuthContext.Provider value={localAuth}>{children}</AuthContext.Provider>;
  return (
    <ClerkProvider publishableKey={publishableKey}>
      <ClerkSession>{children}</ClerkSession>
    </ClerkProvider>
  );
}
