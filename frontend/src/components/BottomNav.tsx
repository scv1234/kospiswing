"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export default function BottomNav() {
    const pathname = usePathname();

    const items = [
        { href: "/", icon: "🏠", label: "홈" },
        { href: "/topdown", icon: "📊", label: "리포트" },
        { href: "/swing", icon: "🚀", label: "스윙" },
        { href: "/journal", icon: "📝", label: "기록" },
    ];

    return (
        <nav className="bottom-nav">
            {items.map((item) => (
                <Link
                    key={item.href}
                    href={item.href}
                    className={pathname === item.href ? "active" : ""}
                >
                    <span className="nav-icon">{item.icon}</span>
                    {item.label}
                </Link>
            ))}
        </nav>
    );
}
