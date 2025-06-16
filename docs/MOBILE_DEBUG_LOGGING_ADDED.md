# 📱 Mobile Number Debug Logging - Added for Troubleshooting

## 🎯 **Problem**
User experiencing profile completion failure, suspected mobile number format mismatch between:
- **Database storage**: `7906986914` (10-digit format)
- **OTPless return**: Possibly `+917906986914` (+91 format)

## 🔧 **Debug Logging Added**

### **1. OTPless Service Level (`app/services/otpless_service.py`)**
```
📱 === OTPLESS MOBILE EXTRACTION DEBUG ===
📱 Raw mobile from OTPLESS: '{mobile_value}'
📱 Mobile type: {type}
📱 Mobile length: {length}
📱 Mobile repr: {repr}
📱 Mobile starts with +: {boolean}
📱 Mobile starts with +91: {boolean}
📱 Mobile is verified: {boolean}
📱 =======================================
```

### **2. OTPless Authentication (`app/api/otpless_auth.py`)**

#### **A. Initial Mobile Analysis**
```
📱 =================== MOBILE DEBUG ===================
📱 OTPless returned mobile: '{mobile}' (type: {type})
📱 Mobile length: {length}
📱 Mobile starts with +91: {boolean}
📱 Mobile starts with 91: {boolean}
📱 Mobile is 10 digits: {boolean}
📱 Mobile is 13 chars (+91XXXXXXXXXX): {boolean}
📱 Raw mobile representation: {repr}
📱 ===================================================
```

#### **B. Mobile Lookup Process**
```
🔍 ============= MOBILE LOOKUP DEBUG =============
🔍 Looking for user by mobile: '{mobile}'
🔍 Step 1: Trying exact match lookup...
✅/❌ EXACT MATCH found/not found: ID={id}, mobile='{db_mobile}', email='{email}'
🔍 Step 2: Trying flexible matching...
✅/❌ FLEXIBLE MATCH found/not found: ID={id}
📱 Mobile format - OTPLESS: '{otpless_mobile}', DB: '{db_mobile}'
📱 User email: '{email}'
📱 User status: {status}
🔍 ============================================
```

#### **C. Flexible Matching Details**
```
📱 === FLEXIBLE MOBILE LOOKUP DEBUG ===
📱 Input mobile: '{mobile}'
📱 Step 1: Exact match lookup for '{mobile}'
📱 ✅/❌ Exact match found/not found: ID={id}, email='{email}'
📱 Step 2: Normalize and search
📱 Normalized '{original}' to '{normalized}'
📱 ✅/❌ Normalized match found/not found: ID={id}, email='{email}'
📱 Step 3: Adding +91 prefix: '{prefixed}'
📱 ✅/❌ +91 prefixed match found/not found: ID={id}, email='{email}'
📱 Step 4: Removing +91 prefix: '{normalized}'
📱 ✅/❌ -91 prefix match found/not found: ID={id}, email='{email}'
📱 =====================================
```

### **3. Profile Completion (`app/api/otpless_auth.py`)**
```
📝 === PROFILE COMPLETION DEBUG ===
📝 Current user ID: {id}
📝 Current user mobile: '{mobile}'
📝 Current user email: '{email}'
📝 Current user name: '{name}'
📝 Current user registration_status: {status}
📝 Current user profile_completed: {boolean}
📝 Profile data email: '{email}'
📝 Profile data name: '{name}'
📝 Profile data date_of_birth: {date}
📝 =================================
```

#### **Profile Email Conflict Checking**
```
📝 Checking email conflicts...
📝 Profile email: '{profile_email}' vs Current email: '{current_email}'
📝 Email is different, checking for conflicts...
📝 Found existing user with email '{email}': ID={id}
📝 Existing user mobile: '{mobile}'
📝 Existing user status: {status}
📝 Current user mobile: '{current_mobile}'
📝 Existing user mobile: '{existing_mobile}'
📝 About to merge - final mobile will be: '{final_mobile}'
✅ Successfully merged accounts for: {email}
✅ Final user mobile: '{mobile}'
```

## 🧪 **How to Use This Logging**

### **Step 1: Run Your Test**
1. Start your backend server
2. Try the OTPless login with your phone number `7906986914`
3. Complete the profile completion process

### **Step 2: Check Backend Logs**
Look for these specific log sections in order:

1. **🔍 OTPless API Response** - What raw data comes from OTPless
2. **📱 MOBILE EXTRACTION** - How the mobile is extracted from OTPless response
3. **📱 MOBILE DEBUG** - Analysis of the mobile format received
4. **🔍 MOBILE LOOKUP** - How the user lookup process works
5. **📱 FLEXIBLE LOOKUP** - Detailed matching attempts
6. **📝 PROFILE COMPLETION** - Profile completion process details

### **Step 3: Key Things to Check**

#### **Mobile Format Questions:**
- What exactly does OTPless return? `7906986914` or `+917906986914`?
- Is the flexible matching working correctly?
- Are both formats being checked during lookup?

#### **User Matching Questions:**
- Is your bulk-imported user found during lookup?
- What's the exact mobile format in your database?
- Is the profile completion failing because of user merging?

## 🎯 **Expected Scenarios**

### **Scenario A: Perfect Match**
```
📱 OTPless returned mobile: '7906986914'
📱 ✅ EXACT MATCH found: ID=abc123, mobile='7906986914'
```

### **Scenario B: Format Mismatch (Fixed by Flexible Matching)**
```
📱 OTPless returned mobile: '+917906986914'
📱 ❌ No exact match found for '+917906986914'
📱 ✅ -91 prefix match found: ID=abc123, email='you@email.com'
```

### **Scenario C: Complete Mismatch (Problem!)**
```
📱 OTPless returned mobile: '+917906986914'
📱 ❌ No exact match found
📱 ❌ No normalized match
📱 ❌ No +91 prefixed match  
📱 ❌ No -91 prefix match
📱 ❌ No user found with any mobile matching strategy
```

## 🚨 **What to Look For**

1. **Mobile Format**: Confirm exactly what OTPless returns
2. **Database Format**: See what's actually stored in your database
3. **Matching Process**: Verify flexible matching is working
4. **Profile Completion**: Check if merging process is successful

## 📋 **Next Steps After Getting Logs**

Once you run the test and get the logs, you'll be able to:

1. **Identify the exact issue** - Format mismatch, lookup failure, or profile completion problem
2. **See the root cause** - Whether it's a normalization issue, database inconsistency, or OTPless format change
3. **Plan the fix** - Adjust the flexible matching logic, fix database data, or handle new OTPless format

---

**🔍 Run your test now and check the backend logs for these detailed debug messages!** 