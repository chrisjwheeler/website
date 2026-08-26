---
layout: default
title: Fiction
permalink: /fiction/
category: fiction
---

<section class="category-page">

    <h1>Fiction</h1>

    <div class="post-list">

        {% assign posts = site.posts
            | where: "category", "fiction" %}

        {% for post in posts %}

        <a href="{{ post.url | relative_url }}"
           class="post-row">

            <span class="post-date">
                {{ post.date | date: "%d.%m.%y" }}
            </span>

            <div>

                <h2>{{ post.title }}</h2>

                {% if post.excerpt %}
                <p>
                    {{ post.excerpt | strip_html | truncate: 140 }}
                </p>
                {% endif %}

            </div>

            <span class="arrow">↗</span>

        </a>

        {% endfor %}

    </div>

</section>
