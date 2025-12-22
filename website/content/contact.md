---
title: "Contact Us"
description: "Get in touch with the PhotoSifter team"
layout: "single"
---

<section class="bg-gradient-to-br from-blue-600 to-indigo-700 text-white py-16">
  <div class="container mx-auto px-6 lg:px-8">
    <h1 class="text-4xl md:text-5xl font-bold mb-4">Contact Us</h1>
    <p class="text-xl text-blue-100">We'd love to hear from you</p>
  </div>
</section>

<section class="py-16 bg-white">
  <div class="container mx-auto px-6 lg:px-8">
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-12 max-w-6xl mx-auto">

      <!-- Contact Form -->
      <div>
        <h2 class="text-2xl font-bold mb-6 text-gray-800">Send a Message</h2>
        <form
          name="contact"
          method="POST"
          data-netlify="true"
          netlify-honeypot="bot-field"
          class="space-y-6"
        >
          <input type="hidden" name="form-name" value="contact">
          <p class="hidden">
            <label>Don't fill this out: <input name="bot-field"></label>
          </p>

          <div>
            <label for="name" class="block text-sm font-medium text-gray-700 mb-2">Name</label>
            <input
              type="text"
              id="name"
              name="name"
              required
              class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-600 focus:border-transparent transition-colors"
              placeholder="Your name"
            >
          </div>

          <div>
            <label for="email" class="block text-sm font-medium text-gray-700 mb-2">Email</label>
            <input
              type="email"
              id="email"
              name="email"
              required
              class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-600 focus:border-transparent transition-colors"
              placeholder="you@example.com"
            >
          </div>

          <div>
            <label for="subject" class="block text-sm font-medium text-gray-700 mb-2">Subject</label>
            <select
              id="subject"
              name="subject"
              required
              class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-600 focus:border-transparent transition-colors"
            >
              <option value="">Select a topic...</option>
              <option value="general">General Question</option>
              <option value="support">Technical Support</option>
              <option value="license">License / Purchase</option>
              <option value="bug">Bug Report</option>
              <option value="feature">Feature Request</option>
            </select>
          </div>

          <div>
            <label for="message" class="block text-sm font-medium text-gray-700 mb-2">Message</label>
            <textarea
              id="message"
              name="message"
              rows="5"
              required
              class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-600 focus:border-transparent transition-colors resize-y"
              placeholder="How can we help?"
            ></textarea>
          </div>

          <button
            type="submit"
            class="w-full bg-blue-600 text-white px-6 py-4 rounded-lg font-bold text-lg hover:bg-blue-700 focus:outline-none focus:ring-4 focus:ring-blue-600 focus:ring-opacity-50 transition-colors"
          >
            Send Message
          </button>
        </form>
      </div>

      <!-- Contact Info -->
      <div>
        <h2 class="text-2xl font-bold mb-6 text-gray-800">Other Ways to Reach Us</h2>

        <div class="space-y-6">
          <div class="flex items-start gap-4">
            <div class="text-3xl">📧</div>
            <div>
              <h3 class="font-bold text-gray-800">Email</h3>
              <a href="mailto:support@photosifter.com" class="text-blue-600 hover:underline">support@photosifter.com</a>
            </div>
          </div>

          <div class="flex items-start gap-4">
            <div class="text-3xl">💬</div>
            <div>
              <h3 class="font-bold text-gray-800">GitHub Issues</h3>
              <p class="text-gray-600 mb-2">For bug reports and feature requests</p>
              <a href="https://github.com/jasonsutter87/photosifter/issues" class="text-blue-600 hover:underline" target="_blank" rel="noopener">Open an Issue</a>
            </div>
          </div>

          <div class="flex items-start gap-4">
            <div class="text-3xl">📖</div>
            <div>
              <h3 class="font-bold text-gray-800">Documentation</h3>
              <p class="text-gray-600 mb-2">Check out our GitHub readme</p>
              <a href="https://github.com/jasonsutter87/photosifter" class="text-blue-600 hover:underline" target="_blank" rel="noopener">View Documentation</a>
            </div>
          </div>
        </div>

        <div class="mt-10 p-6 bg-gray-50 rounded-xl">
          <h3 class="font-bold text-gray-800 mb-3">Response Time</h3>
          <p class="text-gray-600">
            We typically respond within 1-2 business days. Pro license holders receive priority support.
          </p>
        </div>
      </div>

    </div>
  </div>
</section>
