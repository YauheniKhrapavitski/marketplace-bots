import { NextResponse, type NextRequest } from "next/server";
import { z } from "zod";

import { verifyPassword } from "@/lib/auth/password";
import { setDemoSession } from "@/lib/auth/session";
import { prisma } from "@/lib/db/client";

const loginSchema = z.object({
  login: z.string().min(1),
  password: z.string().min(1)
});

export async function POST(request: NextRequest): Promise<NextResponse> {
  const parsed = loginSchema.safeParse(await request.json());
  if (!parsed.success) {
    return NextResponse.json({ error: "Введите логин и пароль" }, { status: 400 });
  }

  const { login, password } = parsed.data;

  try {
    const user = await prisma.user.findUnique({
      where: { login },
      include: { cutterProfile: true }
    });

    if (!user || !user.isActive || !verifyPassword(password, user.passwordHash)) {
      return NextResponse.json({ error: "Неверный логин или пароль" }, { status: 401 });
    }

    await setDemoSession({
      id: user.id,
      role: user.role,
      cutterId: user.cutterProfile?.id,
      displayName: user.displayName
    });

    await prisma.user.update({
      where: { id: user.id },
      data: { failedLoginAttempts: 0, lastLoginAt: new Date() }
    });

    return NextResponse.json({ ok: true, redirectTo: user.role === "ADMIN" ? "/admin" : "/" });
  } catch {
    if ((login === "admin" && password === "admin") || (login === "cutter" && password === "cutter")) {
      await setDemoSession({
        id: login,
        role: login === "admin" ? "ADMIN" : "CUTTER",
        cutterId: login === "admin" ? undefined : "demo-cutter",
        displayName: login === "admin" ? "Администратор" : "Китасов Саша"
      });

      return NextResponse.json({ ok: true, redirectTo: login === "admin" ? "/admin" : "/" });
    }

    return NextResponse.json(
      { error: "База недоступна. Для демо используйте admin/admin или cutter/cutter." },
      { status: 503 }
    );
  }
}
