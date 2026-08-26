import { PrismaClient } from "@prisma/client";
import { randomBytes, scryptSync } from "node:crypto";

const prisma = new PrismaClient();

function hashPassword(password) {
  const salt = randomBytes(16).toString("hex");
  const derivedKey = scryptSync(password, salt, 64).toString("hex");
  return `scrypt:${salt}:${derivedKey}`;
}

const sourcePayload = {
  date: "03.08.2026",
  vinylstudioArticle: "VS-1042",
  name: "Наклейка декоративная, тестовый набор",
  productComment: "Проверить раскладку перед резкой",
  shipmentNumber: "000734512",
  quantity: 2,
  warehouse: "Коледино",
  wildberriesArticle: "WB-990012",
  shipmentComment: "Отгрузить отдельной коробкой",
  status: "Не сделано",
  complexity: 1.25,
  marketplace: "WB",
  fulfillmentType: "ФБС",
  packaging: "Коробка S",
  requestNumber: "REQ-2026-0001"
};

async function main() {
  const admin = await prisma.user.upsert({
    where: { login: "admin" },
    update: { passwordHash: hashPassword("admin"), role: "ADMIN", isActive: true },
    create: {
      login: "admin",
      displayName: "Администратор",
      passwordHash: hashPassword("admin"),
      role: "ADMIN",
      mustChangePassword: false
    }
  });

  const cutter = await prisma.user.upsert({
    where: { login: "cutter" },
    update: { passwordHash: hashPassword("cutter"), role: "CUTTER", isActive: true },
    create: {
      login: "cutter",
      displayName: "Китасов Саша",
      passwordHash: hashPassword("cutter"),
      role: "CUTTER",
      mustChangePassword: false
    }
  });

  const profile = await prisma.cutterProfile.upsert({
    where: { userId: cutter.id },
    update: { displayName: "Китасов Саша", sourceSheet: "Китасов Саша", isActive: true },
    create: {
      userId: cutter.id,
      displayName: "Китасов Саша",
      sourceSheet: "Китасов Саша"
    }
  });

  await prisma.sourceConnection.create({
    data: {
      provider: "google",
      spreadsheetId: process.env.SOURCE_SPREADSHEET_ID || "demo-spreadsheet",
      allowedSheets: ["Китасов Саша"],
      lastSuccessfulSyncAt: new Date()
    }
  });

  const item = await prisma.sourceItem.upsert({
    where: { sourceUid: "demo-source-1" },
    update: {
      cutterId: profile.id,
      sourceSheet: "Китасов Саша",
      sourceRowRef: "Китасов Саша!2:2",
      sourcePayload,
      checksum: "demo-checksum",
      isArchived: false
    },
    create: {
      sourceUid: "demo-source-1",
      cutterId: profile.id,
      sourceSheet: "Китасов Саша",
      sourceRowRef: "Китасов Саша!2:2",
      sourcePayload,
      checksum: "demo-checksum"
    }
  });

  await prisma.itemOverride.upsert({
    where: { itemId_fieldName: { itemId: item.id, fieldName: "status" } },
    update: { value: "Сделано", updatedBy: admin.id, cutterId: profile.id },
    create: {
      itemId: item.id,
      cutterId: profile.id,
      fieldName: "status",
      value: "Сделано",
      updatedBy: admin.id
    }
  });

  console.log("Seed complete: admin/admin and cutter/cutter");
}

main()
  .catch((error) => {
    console.error(error);
    process.exitCode = 1;
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
