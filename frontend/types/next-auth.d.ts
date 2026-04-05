import { DefaultSession } from "next-auth";

declare module "next-auth" {
  interface Session {
    user: DefaultSession["user"] & {
      id: string;
      accessToken?: string;
      subscriptionTier?: string;
    };
  }

  interface User {
    id: string;
    accessToken?: string;
    subscriptionTier?: string;
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    id?: string;
    accessToken?: string;
    subscriptionTier?: string;
  }
}
