'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Separator } from '@/components/ui/separator'
import { useAuth } from '@/contexts/auth-context'
import { apiClient } from '@/lib/api-client'
import { useToast } from '@/components/ui/use-toast'
import { 
  User, 
  Bell, 
  Shield, 
  Palette, 
  Globe, 
  Database,
  FileText,
  Save,
  Key
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'

export default function SettingsPage() {
  const { user } = useAuth()
  const { toast } = useToast()
  
  // Profile settings
  const [profile, setProfile] = useState({
    first_name: '',
    last_name: '',
    email: ''
  })
  
  // Password change
  const [passwordData, setPasswordData] = useState({
    current_password: '',
    new_password: '',
    confirm_password: ''
  })
  
  // Notification preferences
  const [notifications, setNotifications] = useState({
    email_batch_complete: true,
    email_export_ready: true,
    email_weekly_summary: false
  })
  
  // System settings (admin only)
  const [systemSettings, setSystemSettings] = useState({
    auto_process_batches: false,
    default_confidence_threshold: 0.8,
    max_batch_size: 30,
    retention_days: 90
  })

  useEffect(() => {
    if (user) {
      setProfile({
        first_name: user.first_name || '',
        last_name: user.last_name || '',
        email: user.email || ''
      })
    }
  }, [user])

  const updateProfile = async () => {
    try {
      await apiClient.put('/auth/me', profile)
      toast({
        title: 'Profile updated',
        description: 'Your profile has been updated successfully',
      })
    } catch (error: any) {
      toast({
        title: 'Update failed',
        description: error.response?.data?.detail || 'Failed to update profile',
        variant: 'destructive'
      })
    }
  }

  const changePassword = async () => {
    if (passwordData.new_password !== passwordData.confirm_password) {
      toast({
        title: 'Password mismatch',
        description: 'New password and confirmation do not match',
        variant: 'destructive'
      })
      return
    }

    try {
      await apiClient.post('/auth/change-password', {
        current_password: passwordData.current_password,
        new_password: passwordData.new_password
      })
      
      toast({
        title: 'Password changed',
        description: 'Your password has been changed successfully',
      })
      
      // Clear form
      setPasswordData({
        current_password: '',
        new_password: '',
        confirm_password: ''
      })
    } catch (error: any) {
      toast({
        title: 'Password change failed',
        description: error.response?.data?.detail || 'Failed to change password',
        variant: 'destructive'
      })
    }
  }

  const isAdmin = user?.role === 'admin'

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Settings</h1>
        <p className="text-muted-foreground">
          Manage your account and system preferences
        </p>
      </div>

      <Tabs defaultValue="profile" className="space-y-4">
        <TabsList className="grid grid-cols-4 w-full max-w-xl">
          <TabsTrigger value="profile">Profile</TabsTrigger>
          <TabsTrigger value="security">Security</TabsTrigger>
          <TabsTrigger value="notifications">Notifications</TabsTrigger>
          {isAdmin && <TabsTrigger value="system">System</TabsTrigger>}
        </TabsList>

        <TabsContent value="profile" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <User className="h-5 w-5" />
                Profile Information
              </CardTitle>
              <CardDescription>
                Update your personal information
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="first_name">First Name</Label>
                  <Input
                    id="first_name"
                    value={profile.first_name}
                    onChange={(e) => setProfile({ ...profile, first_name: e.target.value })}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="last_name">Last Name</Label>
                  <Input
                    id="last_name"
                    value={profile.last_name}
                    onChange={(e) => setProfile({ ...profile, last_name: e.target.value })}
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  value={profile.email}
                  onChange={(e) => setProfile({ ...profile, email: e.target.value })}
                />
              </div>
              <div className="flex justify-end">
                <Button onClick={updateProfile}>
                  <Save className="mr-2 h-4 w-4" />
                  Save Changes
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="security" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Key className="h-5 w-5" />
                Change Password
              </CardTitle>
              <CardDescription>
                Update your password to keep your account secure
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="current_password">Current Password</Label>
                <Input
                  id="current_password"
                  type="password"
                  value={passwordData.current_password}
                  onChange={(e) => setPasswordData({ ...passwordData, current_password: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="new_password">New Password</Label>
                <Input
                  id="new_password"
                  type="password"
                  value={passwordData.new_password}
                  onChange={(e) => setPasswordData({ ...passwordData, new_password: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="confirm_password">Confirm New Password</Label>
                <Input
                  id="confirm_password"
                  type="password"
                  value={passwordData.confirm_password}
                  onChange={(e) => setPasswordData({ ...passwordData, confirm_password: e.target.value })}
                />
              </div>
              <div className="flex justify-end">
                <Button onClick={changePassword}>
                  <Shield className="mr-2 h-4 w-4" />
                  Change Password
                </Button>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Account Information</CardTitle>
              <CardDescription>
                Your account details and permissions
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex justify-between">
                <span className="text-sm text-muted-foreground">Account ID</span>
                <span className="text-sm font-mono">{user?.id?.slice(0, 8)}</span>
              </div>
              <Separator />
              <div className="flex justify-between">
                <span className="text-sm text-muted-foreground">Role</span>
                <Badge>{user?.role}</Badge>
              </div>
              <Separator />
              <div className="flex justify-between">
                <span className="text-sm text-muted-foreground">Account Created</span>
                <span className="text-sm">{user?.created_at ? new Date(user.created_at).toLocaleDateString() : 'N/A'}</span>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="notifications" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Bell className="h-5 w-5" />
                Email Notifications
              </CardTitle>
              <CardDescription>
                Choose what notifications you want to receive
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="space-y-1">
                  <p className="text-sm font-medium">Batch Processing Complete</p>
                  <p className="text-sm text-muted-foreground">
                    Get notified when your batch processing is finished
                  </p>
                </div>
                <Switch
                  checked={notifications.email_batch_complete}
                  onCheckedChange={(checked) => 
                    setNotifications({ ...notifications, email_batch_complete: checked })
                  }
                />
              </div>
              <Separator />
              <div className="flex items-center justify-between">
                <div className="space-y-1">
                  <p className="text-sm font-medium">Export Ready</p>
                  <p className="text-sm text-muted-foreground">
                    Get notified when your export is ready for download
                  </p>
                </div>
                <Switch
                  checked={notifications.email_export_ready}
                  onCheckedChange={(checked) => 
                    setNotifications({ ...notifications, email_export_ready: checked })
                  }
                />
              </div>
              <Separator />
              <div className="flex items-center justify-between">
                <div className="space-y-1">
                  <p className="text-sm font-medium">Weekly Summary</p>
                  <p className="text-sm text-muted-foreground">
                    Receive a weekly summary of processing activity
                  </p>
                </div>
                <Switch
                  checked={notifications.email_weekly_summary}
                  onCheckedChange={(checked) => 
                    setNotifications({ ...notifications, email_weekly_summary: checked })
                  }
                />
              </div>
              <div className="flex justify-end pt-4">
                <Button>
                  <Save className="mr-2 h-4 w-4" />
                  Save Preferences
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {isAdmin && (
          <TabsContent value="system" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Database className="h-5 w-5" />
                  System Configuration
                </CardTitle>
                <CardDescription>
                  Configure system-wide settings (Admin only)
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center justify-between">
                  <div className="space-y-1">
                    <p className="text-sm font-medium">Auto-process Batches</p>
                    <p className="text-sm text-muted-foreground">
                      Automatically start processing when files are uploaded
                    </p>
                  </div>
                  <Switch
                    checked={systemSettings.auto_process_batches}
                    onCheckedChange={(checked) => 
                      setSystemSettings({ ...systemSettings, auto_process_batches: checked })
                    }
                  />
                </div>
                <Separator />
                <div className="space-y-2">
                  <Label>Confidence Threshold</Label>
                  <div className="flex items-center gap-4">
                    <Input
                      type="number"
                      min="0"
                      max="1"
                      step="0.1"
                      value={systemSettings.default_confidence_threshold}
                      onChange={(e) => 
                        setSystemSettings({ 
                          ...systemSettings, 
                          default_confidence_threshold: parseFloat(e.target.value) 
                        })
                      }
                      className="w-24"
                    />
                    <span className="text-sm text-muted-foreground">
                      Minimum confidence for auto-matching (0-1)
                    </span>
                  </div>
                </div>
                <Separator />
                <div className="space-y-2">
                  <Label>Maximum Batch Size</Label>
                  <div className="flex items-center gap-4">
                    <Input
                      type="number"
                      min="1"
                      max="100"
                      value={systemSettings.max_batch_size}
                      onChange={(e) => 
                        setSystemSettings({ 
                          ...systemSettings, 
                          max_batch_size: parseInt(e.target.value) 
                        })
                      }
                      className="w-24"
                    />
                    <span className="text-sm text-muted-foreground">
                      Maximum file pairs per batch
                    </span>
                  </div>
                </div>
                <Separator />
                <div className="space-y-2">
                  <Label>Data Retention</Label>
                  <div className="flex items-center gap-4">
                    <Input
                      type="number"
                      min="7"
                      max="365"
                      value={systemSettings.retention_days}
                      onChange={(e) => 
                        setSystemSettings({ 
                          ...systemSettings, 
                          retention_days: parseInt(e.target.value) 
                        })
                      }
                      className="w-24"
                    />
                    <span className="text-sm text-muted-foreground">
                      Days to keep processed data
                    </span>
                  </div>
                </div>
                <div className="flex justify-end pt-4">
                  <Button>
                    <Save className="mr-2 h-4 w-4" />
                    Save System Settings
                  </Button>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <FileText className="h-5 w-5" />
                  Export Settings
                </CardTitle>
                <CardDescription>
                  Configure default export behavior
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label>Default Export Format</Label>
                  <select className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm">
                    <option value="pdf">PDF Invoices</option>
                    <option value="csv">CSV Files</option>
                    <option value="both">Both PDF and CSV</option>
                  </select>
                </div>
                <div className="space-y-2">
                  <Label>Include Images in Export</Label>
                  <select className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm">
                    <option value="always">Always Include</option>
                    <option value="never">Never Include</option>
                    <option value="optional">Make Optional</option>
                  </select>
                </div>
                <div className="flex justify-end pt-4">
                  <Button>
                    <Save className="mr-2 h-4 w-4" />
                    Save Export Settings
                  </Button>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        )}
      </Tabs>
    </div>
  )
}