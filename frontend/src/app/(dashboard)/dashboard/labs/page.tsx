"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { fetchCurrentUser, type UserProfile } from "@/lib/api";

export default function LabsPage() {
  const { getToken } = useAuth();
  const [user, setUser] = useState<UserProfile | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadUser() {
      try {
        const token = await getToken();
        if (!token) return;
        const profile = await fetchCurrentUser(token);
        setUser(profile);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load profile");
      } finally {
        setLoading(false);
      }
    }
    loadUser();
  }, [getToken]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <p className="text-muted-foreground">Loading...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center py-12">
        <p className="text-destructive">{error}</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Laboratories</h1>
        <p className="text-muted-foreground">
          Create and manage your labs. Invite teammates to collaborate.
        </p>
      </div>

      {user && (
        <Card className="max-w-md">
          <CardHeader>
            <CardTitle>Your Profile</CardTitle>
          </CardHeader>
          <CardContent className="flex items-center gap-4">
            <Avatar className="h-12 w-12">
              <AvatarImage src={user.avatar_url || undefined} />
              <AvatarFallback>
                {(user.display_name || user.email)
                  .split(" ")
                  .map((n) => n[0])
                  .join("")
                  .toUpperCase()
                  .slice(0, 2)}
              </AvatarFallback>
            </Avatar>
            <div>
              <p className="font-medium">{user.display_name || "No name set"}</p>
              <p className="text-sm text-muted-foreground">{user.email}</p>
            </div>
          </CardContent>
        </Card>
      )}

      <Card className="max-w-md border-dashed">
        <CardContent className="flex flex-col items-center justify-center py-8 text-center">
          <p className="text-muted-foreground">
            No laboratories yet. Lab creation will be available in the next milestone.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
