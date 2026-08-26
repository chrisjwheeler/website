---
layout: default
title: Creative non-fiction
permalink: /creative-non-fiction/
category: creative-non-fiction
---

<section class="category-page">

    <h1>Creative non-fiction</h1>

    <div class="post-list">

        {% assign posts = site.posts
            | where: "category", "creative-non-fiction" %}

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
