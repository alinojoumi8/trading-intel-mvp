import NextAuth from "next-auth"
import Credentials from "next-auth/providers/credentials"

import { getApiBaseUrl } from "@/lib/config"

export const { handlers, signIn, signOut, auth } = NextAuth({
  providers: [
    Credentials({
      name: "credentials",
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" }
      },
      async authorize(credentials) {
        const res = await fetch(`${getApiBaseUrl()}/auth/login`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(credentials)
        })
        if (!res.ok) return null
        const data = await res.json()
        return {
          id: String(data.user_id),
          email: data.email,
          name: data.name,
          accessToken: data.access_token,
          subscriptionTier: data.subscription_tier,
        }
      }
    })
  ],
  session: { strategy: "jwt" },
  pages: { signIn: "/auth/login" },
  callbacks: {
    async jwt({ token, user }) {
      if (user) {
        token.id = user.id
        token.accessToken = user.accessToken
        token.subscriptionTier = user.subscriptionTier
      }
      return token
    },
    async session({ session, token }) {
      if (session.user) {
        session.user.id = token.id as string
        session.user.accessToken = token.accessToken as string | undefined
        session.user.subscriptionTier = token.subscriptionTier as string | undefined
      }
      return session
    }
  }
})
