import NextAuth, { type NextAuthOptions } from 'next-auth';
import CredentialsProvider from 'next-auth/providers/credentials';

/**
 * Mock NextAuth setup — 추후 Google/Apple OAuth 추가.
 * 03-Architecture 6.2: JWT(15min) + Refresh(14d HttpOnly cookie).
 */
const authOptions: NextAuthOptions = {
  providers: [
    CredentialsProvider({
      name: 'Email',
      credentials: {
        email: { label: 'Email', type: 'email' },
      },
      async authorize(credentials) {
        // mock: 이메일이 있으면 통과
        if (!credentials?.email) return null;
        return {
          id: 'mock-user-id',
          email: credentials.email,
          name: 'Mock User',
        };
      },
    }),
  ],
  session: { strategy: 'jwt', maxAge: 60 * 15 },
  pages: { signIn: '/sign-in' },
  secret: process.env.NEXTAUTH_SECRET,
};

const handler = NextAuth(authOptions);
export { handler as GET, handler as POST };
